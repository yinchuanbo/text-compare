import os
import git
import autopep8
import jsbeautifier
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

def format_code(content, filename):
    if not content:
        return ""
    
    ext = os.path.splitext(filename)[1].lower()
    
    try:
        if ext == '.py':
            return autopep8.fix_code(content, options={'max_line_length': 100})
        elif ext in {'.js', '.json', '.css', '.html'}:
            # jsbeautifier default options
            opts = jsbeautifier.default_options()
            opts.indent_size = 4
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
        old_formatted = format_code(old_content, file_path)
        new_formatted = format_code(new_content, file_path)
        
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
    app.run(debug=True, port=5000)
