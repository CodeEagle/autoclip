from pathlib import Path
import sys


def patch_frontend(frontend_root: Path) -> None:
    replacements = {
        "http://localhost:8000/api/v1": "/api/v1",
        "http://127.0.0.1:8000/api/v1": "/api/v1",
        "http://localhost:8000/api": "/api",
        "http://127.0.0.1:8000/api": "/api",
    }

    for path in frontend_root.rglob("*"):
        if path.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        text = path.read_text()
        updated = text
        for source, target in replacements.items():
            updated = updated.replace(source, target)
        updated = updated.replace(
            "`ws://localhost:8000/api/v1/ws/${userId}`",
            "`${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/v1/ws/${userId}`",
        )
        updated = updated.replace(
            "`ws://127.0.0.1:8000/api/v1/ws/${userId}`",
            "`${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/v1/ws/${userId}`",
        )
        if updated != text:
            path.write_text(updated)


def patch_task_utils(backend_root: Path) -> None:
    task_utils = backend_root / "utils" / "task_submission_utils.py"
    if not task_utils.exists():
        return

    text = task_utils.read_text()
    updated = text
    if "import os" not in updated:
        updated = updated.replace("import logging\n", "import logging\nimport os\n", 1)
    updated = updated.replace(
        "r = redis.Redis(host='localhost', port=6379, db=0)",
        "r = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379/0'))",
    )
    if updated != text:
        task_utils.write_text(updated)


def patch_pipeline_adapter(backend_root: Path) -> None:
    pipeline_adapter = backend_root / "services" / "simple_pipeline_adapter.py"
    if not pipeline_adapter.exists():
        return

    text = pipeline_adapter.read_text()
    updated = text

    old = """                else:
                    logger.warning("自动生成字幕失败，创建空大纲")
                    # 创建一个空的大纲文件
                    outlines = []
                    outline_file = metadata_dir / "step1_outline.json"
                    import json
                    with open(outline_file, 'w', encoding='utf-8') as f:
                        json.dump(outlines, f, ensure_ascii=False, indent=2)
"""
    new = """                else:
                    logger.error("自动生成字幕失败，无法继续处理")
                    return {
                        "status": "failed",
                        "project_id": self.project_id,
                        "task_id": self.task_id,
                        "message": "自动生成字幕失败，请上传 SRT 或确认镜像内 Whisper 可用"
                    }
"""
    if old in updated:
        updated = updated.replace(old, new)

    old = """            emit_progress(self.project_id, "SUBTITLE", "字幕处理完成", subpercent=50)
            
            # 阶段3: 内容分析
"""
    new = """            emit_progress(self.project_id, "SUBTITLE", "字幕处理完成", subpercent=50)
            
            if not outlines:
                logger.error("未提取到有效大纲，停止后续处理")
                return {
                    "status": "failed",
                    "project_id": self.project_id,
                    "task_id": self.task_id,
                    "message": "未提取到有效大纲，请检查字幕内容或模型配置"
                }
            
            # 阶段3: 内容分析
"""
    if old in updated:
        updated = updated.replace(old, new)

    if updated != text:
        pipeline_adapter.write_text(updated)


def main() -> int:
    source_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/autoclip-source")
    patch_frontend(source_root / "frontend" / "src")
    backend_root = source_root / "backend"
    patch_task_utils(backend_root)
    patch_pipeline_adapter(backend_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
