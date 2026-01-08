import os
import git
import autopep8
import jsbeautifier
import tempfile
import subprocess
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

STATIC_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.woff', '.woff2', 
    '.ttf', '.eot', '.mp4', '.webm', '.mp3', '.wav', '.pdf', '.zip', 
    '.tar', '.gz', '.7z', '.rar', '.exe', '.dll', '.so', '.dylib', '.bin'
}

def is_static_file(filename):
    ext = os.path.splitext(filename)[1].lower()
    return ext in STATIC_EXTENSIONS

def normalize_template_literals(content):
    result = []
    i = 0
    n = len(content)
    while i < n:
        if content[i:i+2] == '${':
            result.append('${')
            i += 2
            # Skip initial whitespace
            while i < n and content[i].isspace():
                i += 1
            
            # Now capture until matching brace
            start_expr = i
            brace_count = 1
            in_string = False
            string_char = None
            
            # Safe guard against infinite loop or out of bound
            while i < n and brace_count > 0:
                char = content[i]
                
                if in_string:
                    if char == string_char:
                        # Check for escape
                        escaped = False
                        k = i - 1
                        while k >= start_expr and content[k] == '\\':
                            escaped = not escaped
                            k -= 1
                        if not escaped:
                            in_string = False
                else:
                    if char == '"' or char == "'" or char == '`':
                        in_string = True
                        string_char = char
                    elif char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            # Found the closing brace
                            # Extract expression
                            expr = content[start_expr:i]
                            # Trim trailing whitespace from expression
                            expr = expr.rstrip()
                            result.append(expr)
                            result.append('}')
                            i += 1
                            break
                i += 1
            
            # If loop finished without brace_count == 0, it means unclosed brace
            if brace_count > 0:
                 # Just append the rest if structure is invalid
                 pass
        else:
            result.append(content[i])
            i += 1
    return "".join(result)

def format_code(content, filename, ignore_newline=False):
    if not content:
        return ""
    
    ext = os.path.splitext(filename)[1].lower()
    
    try:
        if ext == '.py':
            options = {'max_line_length': 100}
            if ignore_newline:
                options['max_line_length'] = 10000
            return autopep8.fix_code(content, options=options)
        elif ext in {'.js', '.json', '.css', '.html'}:
            # Pre-process JS files to normalize template literals
            if ext in {'.js', '.ts', '.jsx', '.tsx'}:
                 content = normalize_template_literals(content)

            # jsbeautifier default options
            opts = jsbeautifier.default_options()
            opts.indent_size = 4
            opts.indent_char = ' '
            opts.indent_with_tabs = False
            opts.preserve_newlines = not ignore_newline
            opts.max_preserve_newlines = 2
            opts.space_in_paren = False
            opts.space_in_empty_paren = False
            opts.jslint_happy = True
            opts.space_after_anon_function = True
            opts.brace_style = "collapse"
            opts.keep_array_indentation = False
            opts.keep_function_indentation = False
            opts.space_before_conditional = True
            opts.unescape_strings = False
            opts.e4x = True
            
            if ignore_newline:
                opts.wrap_line_length = 0 # Disable wrapping
            else:
                opts.wrap_line_length = 100
                
            return jsbeautifier.beautify(content, opts)
        # Add more formatters here if needed
    except Exception as e:
        print(f"Error formatting {filename}: {e}")
        return content # Fallback to original content
        
    return content

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/get_diff_files', methods=['POST'])
def get_diff_files():
    data = request.json
    repo_path = data.get('repo_path')
    commit_id = data.get('commit_id')
    
    if not repo_path or not commit_id:
        return jsonify({'error': 'Missing repo_path or commit_id'}), 400

    try:
        repo = git.Repo(repo_path)
        commit = repo.commit(commit_id)
        
        # Determine parent commit to compare with
        if commit.parents:
            parent = commit.parents[0]
            diffs = parent.diff(commit)
        else:
            # Initial commit: compare with empty tree
            diffs = commit.diff(git.NULL_TREE)

        file_list = []
        for diff in diffs:
            # a_path is old, b_path is new
            path = diff.b_path if diff.b_path else diff.a_path
            path = path.replace('\\', '/')
            
            if is_static_file(path):
                continue
                
            change_type = diff.change_type # 'A', 'D', 'M', 'R'
            
            file_list.append({
                'path': path,
                'change_type': change_type
            })
            
        return jsonify({'files': file_list})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_file_content', methods=['POST'])
def get_file_content():
    data = request.json
    repo_path = data.get('repo_path')
    commit_id = data.get('commit_id')
    file_path = data.get('file_path')
    ignore_whitespace = data.get('ignore_whitespace', False)
    
    if not repo_path or not commit_id or not file_path:
        return jsonify({'error': 'Missing parameters'}), 400
    
    try:
        repo = git.Repo(repo_path)
        commit = repo.commit(commit_id)
        
        if commit.parents:
            parent = commit.parents[0]
            diffs = parent.diff(commit)
        else:
            diffs = commit.diff(git.NULL_TREE)
            
        target_diff = None
        for diff in diffs:
            path = diff.b_path if diff.b_path else diff.a_path
            if path == file_path:
                target_diff = diff
                break
        
        if not target_diff:
            return jsonify({'error': 'File not found in diff'}), 404
            
        old_content = ""
        new_content = ""
        
        # Get old content
        if target_diff.a_blob:
            try:
                old_content = target_diff.a_blob.data_stream.read().decode('utf-8')
            except UnicodeDecodeError:
                old_content = "<Binary or Non-UTF8 Content>"
        
        # Get new content
        if target_diff.b_blob:
            try:
                new_content = target_diff.b_blob.data_stream.read().decode('utf-8')
            except UnicodeDecodeError:
                new_content = "<Binary or Non-UTF8 Content>"
                
        # Format content
        old_formatted = format_code(old_content, file_path, ignore_newline=ignore_whitespace)
        new_formatted = format_code(new_content, file_path, ignore_newline=ignore_whitespace)
        
        return jsonify({
            'old_content': old_formatted,
            'new_content': new_formatted,
            'file_path': file_path,
            'language': get_language_from_ext(file_path)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_language_from_ext(filename):
    ext = os.path.splitext(filename)[1].lower()
    map = {
        '.py': 'python',
        '.js': 'javascript',
        '.json': 'json',
        '.html': 'html',
        '.css': 'css',
        '.ts': 'typescript',
        '.java': 'java',
        '.c': 'c',
        '.cpp': 'cpp',
        '.xml': 'xml',
        '.sql': 'sql',
        '.md': 'markdown'
    }
    return map.get(ext, 'plaintext')

@app.route('/api/sync_file_diff', methods=['POST'])
def sync_file_diff():
    data = request.json
    repo_path = data.get('repo_path')
    commit_id = data.get('commit_id')
    file_path = data.get('file_path')
    target_roots = data.get('target_roots') # List of strings
    force_overwrite = data.get('force_overwrite', False) # New parameter
    
    if not repo_path or not commit_id or not file_path or not target_roots:
        return jsonify({'error': 'Missing parameters'}), 400
        
    try:
        repo = git.Repo(repo_path)
        commit = repo.commit(commit_id)
        
        # Helper function to try applying patch with different context levels
        def try_patch_and_apply(context_lines=None, allow_reject=False):
            # 1. Generate Diff Patch
            fd, patch_file = tempfile.mkstemp(suffix='.patch')
            os.close(fd)
            
            try:
                with open(patch_file, 'wb') as f:
                    cmd_diff = ['git', 'diff', '--binary']
                    if context_lines is not None:
                        cmd_diff.append(f'-U{context_lines}')
                        
                    if commit.parents:
                        cmd_diff.extend([commit.parents[0].hexsha, commit.hexsha])
                    else:
                        cmd_diff.extend([git.NULL_TREE, commit.hexsha])
                    
                    cmd_diff.append('--')
                    cmd_diff.append(file_path)
                    
                    subprocess.run(cmd_diff, cwd=repo.working_dir, stdout=f, check=True)

                if os.path.getsize(patch_file) == 0:
                     return None, 'No changes found'

                # 2. Apply Patch
                current_results = []
                for target_root in target_roots:
                    target_root = target_root.strip()
                    if not target_root: continue
                    if not os.path.exists(target_root):
                        current_results.append({'target': target_root, 'status': 'error', 'message': 'Directory not found'})
                        continue

                    cmd_apply = [
                        'git', 'apply',
                        '-p1',
                        '--whitespace=nowarn',
                        '--ignore-space-change',
                        '--ignore-whitespace',
                        '--verbose',
                        patch_file
                    ]
                    
                    if context_lines == 0:
                        cmd_apply.insert(2, '--unidiff-zero')
                        
                    if allow_reject:
                        cmd_apply.append('--reject')

                    proc = subprocess.run(cmd_apply, capture_output=True, text=True, cwd=target_root)
                    
                    if proc.returncode == 0:
                        current_results.append({'target': target_root, 'status': 'success'})
                    else:
                        msg = proc.stderr if proc.stderr else proc.stdout
                        
                        # If --reject was used, and we have failure, it means some hunks failed.
                        # We can check if .rej files were created, but git apply usually tells us.
                        if allow_reject and 'Rejected' in msg:
                             current_results.append({'target': target_root, 'status': 'partial', 'message': 'Partial apply. Check .rej files.'})
                        else:
                             current_results.append({'target': target_root, 'status': 'failed', 'message': msg})
                
                return patch_file, current_results

            finally:
                if os.path.exists(patch_file):
                    os.unlink(patch_file)

        # First attempt: Standard context
        _, results = try_patch_and_apply()
        
        final_results = []
        failed_targets = []
        
        for r in results:
            if r['status'] == 'success':
                final_results.append(r)
            else:
                failed_targets.append(r['target'])
                
        if failed_targets:
            # Retry failed targets with -U0
            original_targets = target_roots
            target_roots = failed_targets
            
            _, retry_results = try_patch_and_apply(context_lines=0)
            
            # Check if -U0 failed too
            still_failed = []
            for r in retry_results:
                if r['status'] == 'success':
                    final_results.append(r)
                else:
                    still_failed.append(r['target'])
            
            # If still failed, try --reject (Partial Apply)
            if still_failed:
                 target_roots = still_failed
                 _, reject_results = try_patch_and_apply(context_lines=0, allow_reject=True)
                 
                 final_final_failed = []
                 for r in reject_results:
                     if r['status'] in ['success', 'partial']:
                         final_results.append(r)
                     else:
                         final_final_failed.append(r['target'])
                 
                 # Force Overwrite Option
                 if final_final_failed and force_overwrite:
                     # Get full file content from source
                     # We can reuse get_file_content logic or just read blob
                     try:
                         # Get new content blob
                         target_diff = None
                         if commit.parents:
                             diffs = commit.parents[0].diff(commit)
                         else:
                             diffs = commit.diff(git.NULL_TREE)
                             
                         for d in diffs:
                             p = d.b_path if d.b_path else d.a_path
                             if p == file_path:
                                 target_diff = d
                                 break
                         
                         new_content = None
                         if target_diff and target_diff.b_blob:
                             new_content = target_diff.b_blob.data_stream.read() # Binary read
                         
                         if new_content is not None:
                             for target in final_final_failed:
                                 # Construct full path
                                 # target is the root. file_path is relative.
                                 # file_path might contain forward slashes. os.path.join handles it on Windows if properly split
                                 # but file_path is from git, so forward slashes.
                                 full_dest_path = os.path.join(target, *file_path.split('/'))
                                 
                                 try:
                                     # Ensure dir exists
                                     os.makedirs(os.path.dirname(full_dest_path), exist_ok=True)
                                     with open(full_dest_path, 'wb') as f:
                                         f.write(new_content)
                                     final_results.append({'target': target, 'status': 'success', 'message': 'Forced overwrite'})
                                 except Exception as e:
                                     final_results.append({'target': target, 'status': 'failed', 'message': f'Overwrite failed: {e}'})
                         else:
                             for target in final_final_failed:
                                 final_results.append({'target': target, 'status': 'failed', 'message': 'Could not get new content for overwrite'})
                                 
                     except Exception as e:
                         for target in final_final_failed:
                             final_results.append({'target': target, 'status': 'failed', 'message': f'Force overwrite error: {e}'})
                 else:
                     # Add the failure messages from reject_results for those that failed completely
                     for r in reject_results:
                         if r['target'] in final_final_failed:
                             final_results.append(r)

            target_roots = original_targets
        
        return jsonify({'results': final_results})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/explorer')
def explorer():
    return render_template('explorer.html')

@app.route('/api/scan_directory', methods=['POST'])
def scan_directory():
    data = request.json
    dir_path = data.get('dir_path')
    split_key = data.get('split_key')
    
    if not dir_path:
        return jsonify({'error': 'Missing dir_path'}), 400
        
    if not os.path.exists(dir_path):
        return jsonify({'error': 'Directory does not exist'}), 404
        
    if not os.path.isdir(dir_path):
        return jsonify({'error': 'Path is not a directory'}), 400
        
    file_list = []
    try:
        for root, dirs, files in os.walk(dir_path):
            # Optional: Ignore .git directories to reduce noise
            if '.git' in dirs:
                dirs.remove('.git')
            if '__pycache__' in dirs:
                dirs.remove('__pycache__')
            if 'node_modules' in dirs:
                dirs.remove('node_modules')
                
            for file in files:
                full_path = os.path.join(root, file)
                
                final_path = ""
                
                if split_key:
                     norm_path = os.path.normpath(full_path)
                     # Split path into parts to find the key safely
                     path_parts = norm_path.split(os.sep)
                     
                     # Case insensitive search
                     path_parts_lower = [p.lower() for p in path_parts]
                     split_key_lower = split_key.lower()
                     
                     if split_key_lower in path_parts_lower:
                         try:
                             # Find index of the key
                             idx = path_parts_lower.index(split_key_lower)
                             # Reconstruct path from parts AFTER the key
                             if idx + 1 < len(path_parts):
                                 final_path = os.path.join(*path_parts[idx+1:])
                             else:
                                 final_path = "" # Should not happen for a file
                         except ValueError:
                             final_path = os.path.relpath(full_path, dir_path)
                     else:
                         final_path = os.path.relpath(full_path, dir_path)
                else:
                    # Get relative path normally
                    final_path = os.path.relpath(full_path, dir_path)
                
                # Normalize path separators
                final_path = os.path.normpath(final_path)
                # Force forward slashes
                final_path = final_path.replace('\\', '/')
                if final_path and final_path != ".":
                    file_list.append(final_path)
                
        return jsonify({'files': file_list})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
