"""initial_schema

Revision ID: 50e79179bfd0
Revises: 
Create Date: 2026-05-04 08:29:13.198932

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '50e79179bfd0'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Фиксируем текущее состояние базы данных.
    
    Эта миграция ничего не меняет в схеме, только отмечает,
    что текущая версия схемы соответствует этому revision.
    Все таблицы уже существуют в БД.
    """
    # Таблицы уже существуют, ничего не создаём
    pass


def downgrade() -> None:
    """Откат невозможен, так как это базовая миграция."""
    pass