from flask import Flask, request, jsonify
import subprocess
import threading
import os
import signal

app = Flask(__name__)

# Global variables to track the process
bgmi_process = None
stop_event = threading.Event()

def run_bgmi_server(ip, port, duration, threads):
    global bgmi_process
    try:
        # Command to run the bgmi executable
        command = f"./bgmi {ip} {port} {duration} {threads}"

        # Start the process
        bgmi_process = subprocess.Popen(
            command,
            shell=True,
            preexec_fn=os.setsid,  # Create new process group
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Wait for duration or until stop is requested
        stop_event.wait(timeout=int(duration))

        # If still running, terminate
        if bgmi_process and bgmi_process.poll() is None:
            os.killpg(os.getpgid(bgmi_process.pid), signal.SIGTERM)
            bgmi_process.wait()

    except Exception as e:
        print(f"Error running BGMI: {e}")
    finally:
        stop_event.clear()

@app.route('/start-server', methods=['POST'])
def start_server():
    global bgmi_process, stop_event

    if bgmi_process and bgmi_process.poll() is None:
        return jsonify({"status": "error", "message": "Server already running"}), 400

    data = request.get_json()
    ip = data.get('ip')
    port = data.get('port')
    duration = data.get('duration')
    threads = data.get('threads', 1)  # Default to 1 thread if not specified

    if not all([ip, port, duration]):
        return jsonify({"status": "error", "message": "Missing required parameters (ip, port, duration)"}), 400

    stop_event.clear()
    thread = threading.Thread(
        target=run_bgmi_server,
        args=(ip, port, duration, threads)
    )
    thread.start()

    return jsonify({
        "status": "success",
        "message": "Server started",
        "parameters": {
            "ip": ip,
            "port": port,
            "duration": duration,
            "threads": threads
        }
    })

@app.route('/stop-server', methods=['POST'])
def stop_server():
    global bgmi_process

    if not bgmi_process or bgmi_process.poll() is not None:
        return jsonify({"status": "error", "message": "No server running"}), 400

    try:
        os.killpg(os.getpgid(bgmi_process.pid), signal.SIGTERM)
        bgmi_process.wait()
        return jsonify({"status": "success", "message": "Server stopped"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/status', methods=['GET'])
def status():
    global bgmi_process

    if bgmi_process and bgmi_process.poll() is None:
        return jsonify({
            "status": "running",
            "pid": bgmi_process.pid,
            "return_code": None
        })
    else:
        return jsonify({
            "status": "stopped",
            "pid": None,
            "return_code": bgmi_process.poll() if bgmi_process else None
        })

@app.route('/logs', methods=['GET'])
def logs():
    global bgmi_process

    if not bgmi_process:
        return jsonify({"status": "error", "message": "No server process found"}), 404

    try:
        stdout, stderr = bgmi_process.communicate(timeout=5)
        return jsonify({
            "stdout": stdout,
            "stderr": stderr
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            "status": "warning",
            "message": "Process still running, showing partial logs",
            "stdout": bgmi_process.stdout.read() if bgmi_process.stdout else "",
            "stderr": bgmi_process.stderr.read() if bgmi_process.stderr else ""
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))