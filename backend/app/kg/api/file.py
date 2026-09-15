from __future__ import annotations

from fastapi import APIRouter, Query, UploadFile

from app.kg.response import ok
from app.kg.schemas import CreateFileTaskRequest, CreateFolderRequest, UpdateFileRequest, UpdateFolderRequest
from app.kg.services.file_service import file_service

router = APIRouter()


@router.post("/upload")
async def upload_file(file: UploadFile, folder_id: str = Query(default="")):
    item = await file_service.upload_file(file, folder_id=folder_id)
    return ok({"file_id": item.id, "status": item.status, "file": item.model_dump(mode="json")})


@router.post("/tasks")
async def create_task(payload: CreateFileTaskRequest):
    item = await file_service.create_task(
        doc_code=payload.doc_code.strip(),
        title=payload.title.strip(),
        discipline=payload.discipline.strip(),
        parse_mode=payload.parse_mode,
    )
    return ok({"file_id": item.id, "status": item.status, "file": item.model_dump(mode="json")})


@router.get("/list")
async def list_files():
    files = await file_service.list_files()
    return ok({"files": [item.model_dump(mode="json") for item in files]})


@router.get("/folders/list")
async def list_folders():
    folders = await file_service.list_folders()
    return ok({"folders": [folder.model_dump(mode="json") for folder in folders]})


@router.post("/folders")
async def create_folder(payload: CreateFolderRequest):
    folder = await file_service.create_folder(payload.name.strip())
    return ok({"folder": folder.model_dump(mode="json")})


@router.patch("/folders/{folder_id}")
async def update_folder(folder_id: str, payload: UpdateFolderRequest):
    folder = await file_service.update_folder(folder_id, name=payload.name)
    return ok({"folder": folder.model_dump(mode="json")})


@router.delete("/folders/{folder_id}")
async def delete_folder(folder_id: str):
    await file_service.delete_folder(folder_id)
    return ok({"deleted": True})


@router.get("/{file_id}")
async def get_file(file_id: str):
    item = await file_service.get_file(file_id)
    return ok({"file": item.model_dump(mode="json")})


@router.patch("/{file_id}")
async def update_file(file_id: str, payload: UpdateFileRequest):
    item = await file_service.update_file(file_id, folder_id=payload.folder_id)
    return ok({"file": item.model_dump(mode="json")})


@router.post("/{file_id}/upload")
async def upload_to_task(file_id: str, file: UploadFile):
    item = await file_service.attach_upload(file_id, file)
    return ok({"file_id": item.id, "status": item.status, "file": item.model_dump(mode="json")})


@router.post("/{file_id}/import/{source_file_id}")
async def import_from_library(file_id: str, source_file_id: str):
    item = await file_service.import_from_library(file_id, source_file_id)
    return ok({"file_id": item.id, "status": item.status, "file": item.model_dump(mode="json")})


@router.delete("/{file_id}")
async def delete_file(file_id: str):
    await file_service.delete_file(file_id)
    return ok({"deleted": True})
