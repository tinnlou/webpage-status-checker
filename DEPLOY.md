# 部署指南 (Deployment Guide)

## 方案一：使用 Render 部署 (推荐，免费且长期有效)

Render 是一个云服务平台，提供免费的 Web 服务托管，非常适合本项目。

### 步骤：

1.  **注册账号**：访问 [render.com](https://render.com/) 并使用 GitHub 账号登录。
2.  **创建服务**：
    *   点击右上角的 **New +** 按钮，选择 **Web Service**。
    *   在列表中找到您刚才推送到 GitHub 的仓库 `webpage-status-checker`，点击 **Connect**。
3.  **配置参数**：
    *   **Name**: 随便起个名字，比如 `link-checker-tool`。
    *   **Region**: 选择离您近的（比如 Singapore 或 Oregon）。
    *   **Branch**: `main`。
    *   **Runtime**: 选择 **Python 3**。
    *   **Build Command**: `pip install -r requirements.txt`
    *   **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
    *   **Instance Type**: 选择 **Free**。
4.  **部署**：
    *   点击底部的 **Create Web Service**。
    *   等待几分钟，部署完成后，左上角会显示一个类似 `https://link-checker-tool.onrender.com` 的网址。
    *   把这个网址发给同事即可直接使用！

### 注意事项：
*   **休眠机制**：免费版如果 15 分钟没人访问会自动休眠，下次访问需要等待约 50 秒启动。
*   **数据重置**：免费版的文件系统是临时的。**每次重新部署或重启后，历史检测记录（results.db）会被清空**。但这不影响单次检测任务。

---

## 方案二：使用 ngrok (无需部署，利用本机)

如果您只是想临时演示给同事看，不想折腾云端部署，可以使用内网穿透工具。

### 步骤：

1.  **安装 ngrok**：
    *   Mac 用户在终端运行：`brew install ngrok/ngrok/ngrok` (如果没有 brew，去 [ngrok官网](https://ngrok.com/download) 下载)。
2.  **启动服务**：
    *   确保您的 Python 程序正在运行 (`python main.py`)。
3.  **开启穿透**：
    *   新建一个终端窗口，运行：`ngrok http 8000`
4.  **分享链接**：
    *   终端会显示一个 `https://xxxx-xxxx.ngrok-free.app` 的链接。
    *   把这个链接发给同事，他们就能访问您电脑上运行的服务了。

### 优缺点：
*   **优点**：数据在您本地，速度快，完全免费，无需配置云端环境。
*   **缺点**：您的电脑必须开着且程序必须运行，关机链接就失效。
