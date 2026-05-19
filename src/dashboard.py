import json
from fastapi.responses import HTMLResponse
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_async_db
from src.models import Memory

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(db: AsyncSession = Depends(get_async_db)):
    """
    A dead-simple React page served directly to visualize Memory Health.
    """
    # Calculate simple stats
    total_result = await db.execute(select(func.count(Memory.id)))
    total_memories = total_result.scalar() or 0

    conflict_result = await db.execute(select(func.count(Memory.id)).filter(Memory.confidence < 1.0))
    conflict_count = conflict_result.scalar() or 0

    # Calculate module coverage
    module_result = await db.execute(select(Memory.module))
    modules = module_result.scalars().all()
    
    module_counts = {}
    for mod in modules:
        m_name = mod or "unknown"
        module_counts[m_name] = module_counts.get(m_name, 0) + 1

    stats = {
        "total": total_memories,
        "conflicts": conflict_count,
        "modules": module_counts
    }

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Memory Layer Health</title>
        <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
        <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
        <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-50 p-8">
        <div id="root"></div>
        <script type="text/babel">
            const stats = {json.dumps(stats)};

            function Dashboard() {{
                return (
                    <div className="max-w-4xl mx-auto">
                        <h1 className="text-3xl font-bold mb-8 text-gray-800">🧠 AI Memory Layer Health</h1>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                            <div className="bg-white p-6 rounded-lg shadow border border-gray-100">
                                <h2 className="text-gray-500 text-sm font-semibold uppercase tracking-wider mb-2">
                                    Total Memories
                                </h2>
                                <p className="text-4xl font-bold text-indigo-600">{{stats.total}}</p>
                            </div>
                            <div className="bg-white p-6 rounded-lg shadow border border-gray-100">
                                <h2 className="text-gray-500 text-sm font-semibold uppercase tracking-wider mb-2">
                                    Flagged Conflicts
                                </h2>
                                <p className="text-4xl font-bold text-red-500">{{stats.conflicts}}</p>
                            </div>
                        </div>

                        <div className="bg-white p-6 rounded-lg shadow border border-gray-100">
                            <h2 className="text-xl font-bold text-gray-800 mb-4">Module Coverage Heatmap</h2>
                            <div className="space-y-4">
                                {{Object.entries(stats.modules).map(([mod, count]) => {{
                                    const percentage = (count / Math.max(1, stats.total)) * 100;
                                    return (
                                        <div key={{mod}} className="flex items-center">
                                            <div className="w-32 text-sm font-medium text-gray-600 truncate">
                                                {{mod}}
                                            </div>
                                            <div className="flex-1 ml-4 bg-gray-100 rounded-full h-4 overflow-hidden">
                                                <div
                                                    className="bg-indigo-500 h-full rounded-full"
                                                    style={{{{ width: `${{Math.min(100, percentage)}}%` }}}}
                                                ></div>
                                            </div>
                                            <div className="ml-4 text-sm text-gray-500 w-8 text-right">
                                                {{count}}
                                            </div>
                                        </div>
                                    );
                                }})}}
                            </div>
                            {{Object.keys(stats.modules).length === 0 && (
                                <p className="text-gray-500 text-sm italic">No modules recorded yet.</p>
                            )}}
                        </div>
                    </div>
                );
            }}

            const root = ReactDOM.createRoot(document.getElementById('root'));
            root.render(<Dashboard />);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)
