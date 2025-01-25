import sys
import requests
import os
import re
import tkinter as tk
from tkinter import messagebox
from threading import Thread

class AIWorker(Thread):
    def __init__(self, messages):
        super().__init__()
        self.messages = messages

    def run(self):
        try:
            ai_response = self.call_ai_api()
            self.finished(ai_response)
        except Exception as e:
            self.error(str(e))

    def call_ai_api(self):
        """调用本地 LM Studio 的 OpenAI 兼容 API"""
        url = "http://127.0.0.1:1234/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": "your-model-name",
            "messages": self.messages,
            "max_tokens": 150,
            "temperature": 0.7,
        }
        print(self.messages)  # 检查历史记录是否完整

        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            ai_message = response.json()["choices"][0]["message"]["content"].strip()
            return ai_message
        else:
            raise Exception(f"API 错误: {response.status_code}, {response.text}")

class ChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Chat App")
        self.root.geometry("430x550")

        # 聊天记录文件路径
        self.chat_log_file = "chat_history.txt"

        # 聊天记录列表
        self.messages = []

        # 创建聊天显示区域
        self.chat_display = tk.Text(self.root, wrap=tk.WORD, state=tk.DISABLED, height=10, width=50, font=("Arial", 12))
        self.chat_display.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # 创建输入框和按钮区域
        input_frame = tk.Frame(self.root)
        input_frame.pack(padx=10, pady=10, fill=tk.X, expand=False)

        # 创建输入区域
        self.user_input = tk.Text(input_frame, height=4, width=10, font=("Arial", 12))
        self.user_input.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # 绑定回车键事件，按回车直接发送消息
        self.user_input.bind("<Return>", self.on_return_pressed)

        # 创建按钮
        self.send_button = tk.Button(input_frame, text="发送", command=self.send_message, width=8, font=("Arial", 12))
        self.send_button.pack(side=tk.TOP, padx=5)

        self.clear_button = tk.Button(input_frame, text="清除记录", command=self.clear_chat_history, width=8, font=("Arial", 12))
        self.clear_button.pack(side=tk.BOTTOM, padx=5)

        # 加载历史聊天记录
        self.load_chat_history()

    def on_return_pressed(self, event):
        """按下回车键时发送消息"""
        self.send_message()  # 调用发送消息方法
        return "break"  # 阻止回车键产生换行

    def send_message(self):
        user_message = self.user_input.get("1.0", tk.END).strip()  # 获取多行文本
        if not user_message:
            return

        # 添加用户消息到聊天框
        self.add_message("你", user_message)
        self.user_input.delete("1.0", tk.END)

        # 添加用户消息到消息列表（用于 AI 回复）
        self.messages.append({"role": "user", "content": user_message})

        # 调用 AI 获取回复，传递历史聊天记录
        self.get_ai_response()

    def get_ai_response(self):
        """使用 AI Worker 线程获取 AI 回复"""
        self.ai_worker = AIWorker(self.messages)
        self.ai_worker.finished = self.handle_ai_response
        self.ai_worker.error = self.handle_ai_error
        self.ai_worker.start()

    def handle_ai_response(self, ai_message):
        """处理 AI 回复"""
        self.add_message("AI", ai_message)  # 添加 AI 回复到聊天框
        self.messages.append({"role": "assistant", "content": ai_message})  # 将AI的回复加入消息列表
        self.send_to_tts(ai_message)  # 将 AI 回复文本发送到 TTS 服务

    def handle_ai_error(self, error_message):
        """处理 AI 错误"""
        self.add_message("错误", f"AI 回复失败: {error_message}")

    def add_message(self, sender, content):
        """添加消息到聊天框和保存聊天记录"""
        message = f"{sender}: {content}"  # 在消息内容后加一个空行
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, message + "\n")
        self.chat_display.config(state=tk.DISABLED)
        # 判断聊天记录文件是否有内容，如果没有就加上换行符
        if os.path.exists(self.chat_log_file) and os.path.getsize(self.chat_log_file) > 0:
            # 文件存在且有内容，需要加换行符
            self.save_chat_history("\n" + message)
        else:
            # 文件不存在或为空，不添加换行符
            self.save_chat_history(message)

    def clean_text_for_tts(self, text):
        """清理文本，去掉 ** 之间的内容"""
        cleaned_text = re.sub(r'\*.*?\*', '', text)
        return cleaned_text.strip()

    def send_to_tts(self, text):
        """将 AI 回复的文本清理后发送到 TTS 服务"""
        try:
            cleaned_text = self.clean_text_for_tts(text)  # 清理文本
            url = "http://127.0.0.1:5000/receive_text"  # 假设第二个程序在端口5000监听
            data = {"text": cleaned_text}

            response = requests.post(url, json=data)
            response.raise_for_status()  # 如果失败，会抛出异常
            print("Text sent to TTS service successfully.")
        except Exception as e:
            print("错误", f"TTS 服务调用失败: {e}")

    def save_chat_history(self, message):
        """将新的聊天记录追加保存到文本文件中"""
        with open(self.chat_log_file, "a", encoding="utf-8") as file:
            file.write(message)

    def load_chat_history(self):
        """加载历史聊天记录，并更新聊天显示区域和消息列表"""
        if os.path.exists(self.chat_log_file):
            print(f"加载聊天记录文件：{self.chat_log_file}")  # 确认文件路径
            with open(self.chat_log_file, "r", encoding="utf-8") as file:
                chat_history = file.readlines()
                for line in chat_history:
                    print(f"加载历史记录: {line.strip()}")  # 打印每行记录，帮助调试
                    self.chat_display.config(state=tk.NORMAL)
                    self.chat_display.insert(tk.END, line.strip() + "\n")
                    self.chat_display.config(state=tk.DISABLED)
                    # 重新构建消息列表
                    if line.startswith("你:"):
                        self.messages.append({"role": "user", "content": line[2:].strip()})
                    elif line.startswith("AI:"):
                        self.messages.append({"role": "assistant", "content": line[4:].strip()})
        else:
            print(f"聊天记录文件不存在：{self.chat_log_file}")

    def clear_chat_history(self):
        """清空聊天记录，包括显示区域和历史文件"""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete("1.0", tk.END)
        self.chat_display.config(state=tk.DISABLED)
        self.messages = []
        if os.path.exists(self.chat_log_file):
            with open(self.chat_log_file, "w", encoding="utf-8") as file:
                file.truncate()
        messagebox.showinfo("清除记录", "聊天记录已清空。")

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatApp(root)
    root.mainloop()
