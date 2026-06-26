from __future__ import annotations
import os
import time
import httpx
import gradio as gr

# Quand monté dans FastAPI (même process), on appelle localhost sur le même port
_port = os.getenv("PORT", "8000")
API_BASE = os.getenv("API_BASE", f"http://localhost:{_port}")
POLL_INTERVAL = 2  # seconds


def process_file(file, task: str, question: str) -> tuple[str, str]:
    """Upload file to backend and poll until the job finishes."""
    if file is None:
        return "No file selected.", ""

    # ---- Upload ----
    try:
        with open(file.name, "rb") as f:
            filename = file.name.replace("\\", "/").split("/")[-1]
            mime = "application/pdf" if filename.lower().endswith(".pdf") else "text/plain"
            resp = httpx.post(
                f"{API_BASE}/upload",
                files={"file": (filename, f, mime)},
                data={"task": task, "question": question or ""},
                timeout=30,
            )
    except httpx.ConnectError:
        return "Cannot reach API server. Make sure the backend is running.", ""

    if resp.status_code != 202:
        return f"Upload failed ({resp.status_code}): {resp.text}", ""

    job_id = resp.json()["job_id"]
    status_msg = f"Job created: {job_id}\nStatus: PENDING"

    # ---- Poll ----
    while True:
        time.sleep(POLL_INTERVAL)
        try:
            poll = httpx.get(f"{API_BASE}/result/{job_id}", timeout=10)
        except httpx.ConnectError:
            return "Lost connection to API server.", ""

        data = poll.json()
        current_status = data["status"]
        status_msg = f"Job: {job_id}\nStatus: {current_status}"

        if current_status == "COMPLETED":
            return status_msg, data.get("result", "")
        if current_status == "FAILED":
            return status_msg, f"Error: {data.get('error', 'Unknown error')}"
        # Still PENDING or RUNNING — keep polling (Gradio blocks the fn thread)


# ---- UI Layout ----
with gr.Blocks(title="AI File Processor") as demo:
    gr.Markdown("# AI File Processing Pipeline")
    gr.Markdown(
        "Upload a **TXT** or **PDF** file (max 5 MB), choose an AI task, and get insights."
    )

    with gr.Row():
        with gr.Column(scale=1):
            file_input = gr.File(
                label="Upload File",
                file_types=[".txt", ".pdf"],
            )
            task_radio = gr.Radio(
                choices=["summarize", "keywords", "sentiment", "qa"],
                value="summarize",
                label="AI Task",
            )
            question_box = gr.Textbox(
                label="Question (required for Q&A task)",
                placeholder="What is this document about?",
                visible=False,
            )
            submit_btn = gr.Button("Process File", variant="primary")

        with gr.Column(scale=1):
            status_box = gr.Textbox(label="Status", lines=3, interactive=False)
            result_box = gr.Textbox(label="AI Output", lines=10, interactive=False)

    # Show/hide question box based on task
    task_radio.change(
        fn=lambda t: gr.update(visible=(t == "qa")),
        inputs=task_radio,
        outputs=question_box,
    )

    submit_btn.click(
        fn=process_file,
        inputs=[file_input, task_radio, question_box],
        outputs=[status_box, result_box],
    )

    gr.Markdown(
        "**Note:** The UI polls the backend every 2 seconds until the job completes."
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port, share=False, theme=gr.themes.Soft())
