import uvicorn
import gradio as gr
from backend.main import app as fastapi_app

# Gradio preview UI so Hugging Face Space displays a healthy status page
with gr.Blocks(title="MusicTool API") as demo:
    gr.Markdown("""
    # ⚡ Free Music & Social Video Downloader API
    **Status:** Server is Online and Ready! 🚀
    
    This API backend powers https://freemusicdownload.site
    """)

# Mount FastAPI app so /api/download and /api/file/{filename} work directly
app = gr.mount_gradio_app(fastapi_app, demo, path="/")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
