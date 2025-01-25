import os
import requests
import subprocess
import sounddevice as sd
import soundfile as sf
import psutil
import tkinter as tk
from tkinter import messagebox
from threading import Thread
from flask import Flask, request, jsonify
from werkzeug.serving import make_server

class TTSWorker(Thread):
    def __init__(self, text, callback):
        super().__init__()
        self.text = text
        self.callback = callback

    def run(self):
        try:
            params = {
                "refer_wav_path": r"D:\BaiduNetdiskDownload\芭芭拉\在教会的记载里，这件怪事被称为湿漉的七天神像.wav",
                "prompt_text": "在教会的记载里，这件怪事被称为湿漉的七天神像",
                "prompt_language": "zh",
                "text": self.text,
                "text_language": "zh"
            }

            response = requests.get('http://127.0.0.1:9880/', params=params, timeout=100)
            response.raise_for_status()

            file_path = 'temp.wav'
            with open(file_path, 'wb') as f:
                f.write(response.content)

            data, samplerate = sf.read(file_path)
            sd.play(data, samplerate)
            sd.wait()
            self.callback(True)
        except Exception as e:
            self.callback(False, str(e))

class WorkerThread(Thread):
    def run(self):
        path = r"D:\GPT-SoVITS-v2-240821\GPT-SoVITS-v2-240821"
        os.chdir(path)
        subprocess.run([r'runtime\python.exe', 'api.py', '-g',
                        r"D:\BaiduNetdiskDownload\芭芭拉\芭芭拉-e10.ckpt", '-s',
                        r"D:\BaiduNetdiskDownload\芭芭拉\芭芭拉_e10_s220.pth"])

class MyWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("Text to Speech")
        self.root.geometry("300x400")  # 设置窗口的初始大小
        self.flask_thread = None

        # 创建控件
        self.text_te = tk.Text(self.root, height=10, width=20)
        self.text_te.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        self.start_service_btn = tk.Button(self.root, text="Start Service", command=self.start_service_btn_clicked, width=35)
        self.start_service_btn.pack(pady=5)

        self.close_service_btn = tk.Button(self.root, text="Close Service", command=self.close_service_btn_clicked, width=35)
        self.close_service_btn.pack(pady=5)

        self.tts_btn = tk.Button(self.root, text="TTS", command=self.tts_btn_clicked, width=35)
        self.tts_btn.pack(pady=5)

    def start_service_btn_clicked(self):
        self.service_thread = WorkerThread()
        self.service_thread.start()

        # 启动 Flask 服务线程
        self.flask_thread = FlaskThread(self)
        self.flask_thread.start()

    @staticmethod
    def close_service_btn_clicked():
        port = 9880
        # 查找占用指定端口的进程
        for conn in psutil.net_connections():
            if conn.status == psutil.CONN_LISTEN and conn.laddr.port == port:
                pid = conn.pid
                try:
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=True)
                    print(f"Process with PID {pid} using port {port} terminated.")
                except subprocess.CalledProcessError as e:
                    print(f"Failed to terminate process with PID {pid}: {e}")
                return
        print(f"No process found using port {port}.")

    def tts_btn_clicked(self):
        text = self.text_te.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("Input Error", "Input text is empty!")
            return

        self.tts_worker = TTSWorker(text, self.on_tts_finished)
        self.tts_worker.start()

        self.tts_btn.config(state=tk.DISABLED)
        print("TTS process started...")

    def on_tts_finished(self, success, error_message=None):
        if success:
            self.tts_btn.config(state=tk.NORMAL)
            print("TTS process finished.")
        else:
            self.tts_btn.config(state=tk.NORMAL)
            print(f"TTS process failed: {error_message}")

    def receive_text_from_ai(self, text):
        """接收来自 AI 的文本，并触发 TTS。"""
        if text.strip():
            print(f"Received text from AI: {text}")
            self.text_te.delete("1.0", "end")
            self.text_te.insert("1.0", text)  # 显示文本到文本框
            self.tts_btn_clicked()  # 自动触发 TTS 语音合成

    def close(self):
        print("Closing service...")
        self.close_service_btn_clicked()
        if self.flask_thread:
            self.flask_thread.stop_flask()  # 停止 Flask 线程

        # 退出 Tkinter 主循环
        self.root.quit()
        self.root.destroy()

class FlaskThread(Thread):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self._stop_event = False
        self.server = None

    def run(self):
        try:
            # 创建 Flask 服务器
            print("Starting Flask server on 127.0.0.1:5000...")
            self.server = make_server('127.0.0.1', 5000, flask_app)
            self.server.serve_forever()
        except Exception as e:
            print(f"Error in Flask server: {e}")

    def stop_flask(self):
        if self.server:
            print("Stopping Flask server...")
            self.server.shutdown()  # 关闭 Flask 服务器
        self._stop_event = True

# 创建 Flask 应用，避免变量名冲突
flask_app = Flask(__name__)

@flask_app.route('/receive_text', methods=['POST'])
def receive_text():
    try:
        data = request.get_json()
        text = data.get('text', '')

        if not text:
            return jsonify({"message": "No text provided"}), 400

        print(f"Received text from AI: {text}")
        window.receive_text_from_ai(text)  # 调用窗口的接收函数
        return jsonify({"message": "Text received and TTS triggered"}), 200
    except Exception as e:
        print(f"Error in Flask route: {e}")
        return jsonify({"message": f"Error: {str(e)}"}), 500


if __name__ == "__main__":
    # 创建 Tkinter 窗口
    root = tk.Tk()
    window = MyWindow(root)

    # 启动 Flask 服务线程（不建议启用这条代码，虽然没bug但是.....）
    # window.start_service_btn_clicked()

    root.protocol("WM_DELETE_WINDOW", window.close)  # 点击关闭窗口时调用 close()
    root.mainloop()
