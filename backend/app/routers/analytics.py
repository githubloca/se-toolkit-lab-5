"""Router for analytics endpoints.

Each endpoint performs SQL aggregation queries on the interaction data
populated by the ETL pipeline. All endpoints require a `lab` query
parameter to filter results by lab (e.g., "lab-01").
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models.interaction import InteractionLog
from app.models.item import ItemRecord
from app.models.learner import Learner

router = APIRouter()


@router.get("/scores")
async def get_scores(
    lab: str = Query(..., description="Lab identifier, e.g. 'lab-01'"),
    session: AsyncSession = Depends(get_session),
):
    """Score distribution histogram for a given lab.

    Find the lab item by matching title (e.g. "lab-04" → title contains "Lab 04")
    Find all tasks that belong to this lab (parent_id = lab.id)
    Query interactions for these items that have a score
    Group scores into buckets: "0-25", "26-50", "51-75", "76-100"
      using CASE WHEN expressions
    Return a JSON array:
      [{"bucket": "0-25", "count": 12}, {"bucket": "26-50", "count": 8}, ...]
    Always return all four buckets, even if count is 0
    """
    from sqlmodel import select

    # Convert "lab-04" to "Lab 04" pattern for title matching
    lab_number = lab.replace("lab-", "Lab ")

    # Find the lab
    lab_stmt = select(ItemRecord).where(
        ItemRecord.type == "lab",
        ItemRecord.title.like(f"%{lab_number}%")
    )
    lab_result = await session.exec(lab_stmt)
    lab_item = lab_result.first()

    if lab_item is None:
        return [
            {"bucket": "0-25", "count": 0},
            {"bucket": "26-50", "count": 0},
            {"bucket": "51-75", "count": 0},
            {"bucket": "76-100", "count": 0},
        ]

    # Find all tasks for this lab
    tasks_stmt = select(ItemRecord.id).where(
        ItemRecord.parent_id == lab_item.id
    )
    tasks_result = await session.exec(tasks_stmt)
    task_ids = tasks_result.all()

    # Include lab itself and all tasks
    item_ids = [lab_item.id] + list(task_ids)

    # Query interactions with scores for these items
    bucket_expr = case(
        (InteractionLog.score <= 25, "0-25"),
        (InteractionLog.score <= 50, "26-50"),
        (InteractionLog.score <= 75, "51-75"),
        else_="76-100",
    )

    stmt = (
        select(bucket_expr.label("bucket"), func.count().label("count"))
        .where(
            InteractionLog.item_id.in_(item_ids),
            InteractionLog.score.isnot(None)
        )
        .group_by(bucket_expr)
    )

    results = await session.exec(stmt)
    rows = results.all()

    # Build result with all buckets
    bucket_counts = {"0-25": 0, "26-50": 0, "51-75": 0, "76-100": 0}
    for bucket, count in rows:
        bucket_counts[bucket] = count

    return [
        {"bucket": "0-25", "count": bucket_counts["0-25"]},
        {"bucket": "26-50", "count": bucket_counts["26-50"]},
        {"bucket": "51-75", "count": bucket_counts["51-75"]},
        {"bucket": "76-100", "count": bucket_counts["76-100"]},
    ]


@router.get("/pass-rates")
async def get_pass_rates(
    lab: str = Query(..., description="Lab identifier, e.g. 'lab-01'"),
    session: AsyncSession = Depends(get_session),
):
    """Per-task pass rates for a given lab.

    Find the lab item and its child task items
    For each task, compute:
      - avg_score: average of interaction scores (round to 1 decimal)
      - attempts: total number of interactions
    Return a JSON array:
      [{"task": "Repository Setup", "avg_score": 92.3, "attempts": 150}, ...]
    Order by task title
    """
    from sqlmodel import select

    # Convert "lab-04" to "Lab 04" pattern for title matching
    lab_number = lab.replace("lab-", "Lab ")

    # Find the lab
    lab_stmt = select(ItemRecord).where(
        ItemRecord.type == "lab",
        ItemRecord.title.like(f"%{lab_number}%")
    )
    lab_result = await session.exec(lab_stmt)
    lab_item = lab_result.first()

    if lab_item is None:
        return []

    # Find all tasks for this lab
    tasks_stmt = select(ItemRecord).where(
        ItemRecord.parent_id == lab_item.id
    ).order_by(ItemRecord.title)
    tasks_result = await session.exec(tasks_stmt)
    tasks = tasks_result.all()

    result = []
    for task in tasks:
        # Get interactions for this task
        stmt = select(
            func.avg(InteractionLog.score).label("avg_score"),
            func.count().label("attempts")
        ).where(InteractionLog.item_id == task.id)

        query_result = await session.exec(stmt)
        row = query_result.first()

        if row and row.attempts > 0:
            avg_score = round(float(row.avg_score), 1) if row.avg_score else 0.0
            result.append({
                "task": task.title,
                "avg_score": avg_score,
                "attempts": row.attempts,
            })

    return result


@router.get("/timeline")
async def get_timeline(
    lab: str = Query(..., description="Lab identifier, e.g. 'lab-01'"),
    session: AsyncSession = Depends(get_session),
):
    """Submissions per day for a given lab.

    Find the lab item and its child task items
    Group interactions by date (use func.date(created_at))
    Count the number of submissions per day
    Return a JSON array:
      [{"date": "2026-02-28", "submissions": 45}, ...]
    Order by date ascending
    """
    from sqlmodel import select

    # Convert "lab-04" to "Lab 04" pattern for title matching
    lab_number = lab.replace("lab-", "Lab ")

    # Find the lab
    lab_stmt = select(ItemRecord).where(
        ItemRecord.type == "lab",
        ItemRecord.title.like(f"%{lab_number}%")
    )
    lab_result = await session.exec(lab_stmt)
    lab_item = lab_result.first()

    if lab_item is None:
        return []

    # Find all tasks for this lab
    tasks_stmt = select(ItemRecord.id).where(
        ItemRecord.parent_id == lab_item.id
    )
    tasks_result = await session.exec(tasks_stmt)
    task_ids = tasks_result.all()

    # Include lab itself and all tasks
    item_ids = [lab_item.id] + list(task_ids)

    # Group by date
    date_col = func.date(InteractionLog.created_at).label("date")
    stmt = (
        select(date_col, func.count().label("submissions"))
        .where(InteractionLog.item_id.in_(item_ids))
        .group_by(date_col)
        .order_by(date_col)
    )

    results = await session.exec(stmt)
    rows = results.all()

    return [
        {"date": str(row.date), "submissions": row.submissions}
        for row in rows
    ]


@router.get("/groups")
async def get_groups(
    lab: str = Query(..., description="Lab identifier, e.g. 'lab-01'"),
    session: AsyncSession = Depends(get_session),
):
    """Per-group performance for a given lab.

    Find the lab item and its child task items
    Join interactions with learners to get student_group
    For each group, compute:
      - avg_score: average score (round to 1 decimal)
      - students: count of distinct learners
    Return a JSON array:
      [{"group": "B23-CS-01", "avg_score": 78.5, "students": 25}, ...]
    Order by group name
    """
    from sqlmodel import select

    # Convert "lab-04" to "Lab 04" pattern for title matching
    lab_number = lab.replace("lab-", "Lab ")

    # Find the lab
    lab_stmt = select(ItemRecord).where(
        ItemRecord.type == "lab",
        ItemRecord.title.like(f"%{lab_number}%")
    )
    lab_result = await session.exec(lab_stmt)
    lab_item = lab_result.first()

    if lab_item is None:
        return []

    # Find all tasks for this lab
    tasks_stmt = select(ItemRecord.id).where(
        ItemRecord.parent_id == lab_item.id
    )
    tasks_result = await session.exec(tasks_stmt)
    task_ids = tasks_result.all()

    # Include lab itself and all tasks
    item_ids = [lab_item.id] + list(task_ids)

    # Join with learners and group by student_group
    stmt = (
        select(
            Learner.student_group.label("group"),
            func.avg(InteractionLog.score).label("avg_score"),
            func.count(Learner.id.distinct()).label("students")
        )
        .join(InteractionLog, InteractionLog.learner_id == Learner.id)
        .where(InteractionLog.item_id.in_(item_ids))
        .group_by(Learner.student_group)
        .order_by(Learner.student_group)
    )

    results = await session.exec(stmt)
    rows = results.all()

    return [
        {
            "group": row.group,
            "avg_score": round(float(row.avg_score), 1) if row.avg_score else 0.0,
            "students": row.students,
        }
        for row in rows
    ]
