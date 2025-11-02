from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.models import User, CustomPrompt
from app.schemas import PromptCreate, PromptUpdate, PromptResponse
from datetime import datetime

router = APIRouter(prefix="/prompts", tags=["prompts"])


def get_current_user(card_key: str, db: Session = Depends(get_db)) -> User:
    """获取当前用户"""
    user = db.query(User).filter(
        User.card_key == card_key,
        User.is_active == True
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的卡密"
        )
    
    # 更新最后使用时间
    user.last_used = datetime.utcnow()
    db.commit()
    
    return user


@router.get("/system", response_model=List[PromptResponse])
async def get_system_prompts(db: Session = Depends(get_db)):
    """获取系统预设提示词"""
    prompts = db.query(CustomPrompt).filter(
        CustomPrompt.is_system == True
    ).all()
    return prompts


@router.get("/", response_model=List[PromptResponse])
async def get_user_prompts(
    card_key: str,
    stage: str = None,
    db: Session = Depends(get_db)
):
    """获取用户自定义提示词"""
    user = get_current_user(card_key, db)
    
    query = db.query(CustomPrompt).filter(CustomPrompt.user_id == user.id)
    
    if stage:
        query = query.filter(CustomPrompt.stage == stage)
    
    prompts = query.all()
    return prompts


@router.post("/", response_model=PromptResponse)
async def create_prompt(
    card_key: str,
    prompt_data: PromptCreate,
    db: Session = Depends(get_db)
):
    """创建自定义提示词"""
    user = get_current_user(card_key, db)
    
    # 如果设置为默认,取消该阶段其他默认提示词
    if prompt_data.is_default:
        db.query(CustomPrompt).filter(
            CustomPrompt.user_id == user.id,
            CustomPrompt.stage == prompt_data.stage,
            CustomPrompt.is_default == True
        ).update({"is_default": False})
    
    prompt = CustomPrompt(
        user_id=user.id,
        name=prompt_data.name,
        stage=prompt_data.stage,
        content=prompt_data.content,
        is_default=prompt_data.is_default,
        is_system=False
    )
    
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    
    return prompt


@router.put("/{prompt_id}", response_model=PromptResponse)
async def update_prompt(
    prompt_id: int,
    card_key: str,
    prompt_data: PromptUpdate,
    db: Session = Depends(get_db)
):
    """更新提示词"""
    user = get_current_user(card_key, db)
    
    prompt = db.query(CustomPrompt).filter(
        CustomPrompt.id == prompt_id,
        CustomPrompt.user_id == user.id
    ).first()
    
    if not prompt:
        raise HTTPException(status_code=404, detail="提示词不存在")
    
    # 如果设置为默认,取消该阶段其他默认提示词
    if prompt_data.is_default:
        db.query(CustomPrompt).filter(
            CustomPrompt.user_id == user.id,
            CustomPrompt.stage == prompt.stage,
            CustomPrompt.is_default == True,
            CustomPrompt.id != prompt_id
        ).update({"is_default": False})
    
    # 更新字段
    if prompt_data.name is not None:
        prompt.name = prompt_data.name
    if prompt_data.content is not None:
        prompt.content = prompt_data.content
    if prompt_data.is_default is not None:
        prompt.is_default = prompt_data.is_default
    
    db.commit()
    db.refresh(prompt)
    
    return prompt


@router.delete("/{prompt_id}")
async def delete_prompt(
    prompt_id: int,
    card_key: str,
    db: Session = Depends(get_db)
):
    """删除提示词"""
    user = get_current_user(card_key, db)
    
    prompt = db.query(CustomPrompt).filter(
        CustomPrompt.id == prompt_id,
        CustomPrompt.user_id == user.id
    ).first()
    
    if not prompt:
        raise HTTPException(status_code=404, detail="提示词不存在")
    
    db.delete(prompt)
    db.commit()
    
    return {"message": "提示词已删除"}


@router.post("/{prompt_id}/set-default")
async def set_default_prompt(
    prompt_id: int,
    card_key: str,
    db: Session = Depends(get_db)
):
    """设置默认提示词"""
    user = get_current_user(card_key, db)
    
    prompt = db.query(CustomPrompt).filter(
        CustomPrompt.id == prompt_id,
        CustomPrompt.user_id == user.id
    ).first()
    
    if not prompt:
        raise HTTPException(status_code=404, detail="提示词不存在")
    
    # 取消该阶段其他默认提示词
    db.query(CustomPrompt).filter(
        CustomPrompt.user_id == user.id,
        CustomPrompt.stage == prompt.stage,
        CustomPrompt.is_default == True
    ).update({"is_default": False})
    
    # 设置为默认
    prompt.is_default = True
    db.commit()
    
    return {"message": "已设置为默认提示词"}
