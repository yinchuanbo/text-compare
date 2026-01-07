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

if __name__ == '__main__':
    app.run(debug=True, port=5000)
