from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import chromadb
from chromadb.config import Settings
import requests
import json
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PM Copilot - Agentic Server")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# NVIDIA API Configuration
NVIDIA_API_KEY = "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"
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL_NAME = "nvidia/nvidia-nemotron-nano-9b-v2"

# Initialize ChromaDB
chroma_client = chromadb.PersistentClient(
    path="./chroma_db",
    settings=Settings(anonymized_telemetry=False)
)

try:
    collection = chroma_client.get_collection(name="pm_documents")
    logger.info(f"Loaded existing collection with {collection.count()} documents")
except:
    collection = chroma_client.create_collection(name="pm_documents")
    logger.info("Created new ChromaDB collection")

# In-memory storage for actions and alerts (in production, use a real database)
actions_db = []
alerts_db = []

# Request models
class ChatRequest(BaseModel):
    message: str

class ActionCreate(BaseModel):
    title: str
    description: str
    assignee: str
    due_date: str
    source: str
    priority: str = "medium"

class AlertCreate(BaseModel):
    title: str
    description: str
    priority: str  # critical, warning, info
    source: str


# =========================
# AGENTIC SYSTEM CORE
# =========================

class AgenticPMCopilot:
    """
    The core agentic system that:
    1. Analyzes user queries to determine intent
    2. Routes to appropriate tools/data sources
    3. Executes proactive monitoring
    4. Generates actions and alerts automatically
    """
    
    def __init__(self, collection, nvidia_api_key):
        self.collection = collection
        self.api_key = nvidia_api_key
        self.intents = {
            "blocker_check": ["blocker", "blocked", "stuck", "impediment", "issue"],
            "status_update": ["status", "progress", "update", "where are we"],
            "team_health": ["team", "workload", "capacity", "burnout"],
            "sprint_analysis": ["sprint", "velocity", "burndown", "points"],
            "risk_assessment": ["risk", "concern", "problem", "delay"]
        }
    
    def classify_intent(self, query: str) -> str:
        """Classify user query intent using keyword matching"""
        query_lower = query.lower()
        
        for intent, keywords in self.intents.items():
            if any(keyword in query_lower for keyword in keywords):
                return intent
        
        return "general_query"
    
    def retrieve_context(self, query: str, n_results: int = 3) -> List[Dict]:
        """Retrieve relevant context from ChromaDB"""
        if self.collection.count() == 0:
            return []
        
        results = self.collection.query(
            query_texts=[query],
            n_results=min(n_results, self.collection.count())
        )
        
        context_docs = []
        if results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                context_docs.append({
                    "content": doc,
                    "metadata": metadata
                })
        
        return context_docs
    
    def generate_response(self, query: str, context: List[Dict]) -> str:
        """Generate AI response using NVIDIA API with context"""
        
        # Build context string
        context_str = "\n\n".join([
            f"Document ({doc['metadata'].get('source', 'unknown')}):\n{doc['content']}"
            for doc in context
        ])
        
        system_prompt = """You are an intelligent PM Copilot assistant. You help product managers by:
- Analyzing project data from meetings, Slack, Jira, GitHub, etc.
- Identifying blockers, risks, and action items
- Providing status updates and insights
- Being proactive about potential issues

Use the provided context to give accurate, specific answers. If you identify any:
- CRITICAL BLOCKERS → Mention them prominently
- ACTION ITEMS → Be clear about who should do what
- RISKS → Call them out explicitly

Be concise but thorough. Use bullet points when listing multiple items."""

        user_prompt = f"""Context from project data:
{context_str if context_str else "No specific context available."}

User question: {query}

Provide a helpful response based on the context and your PM expertise."""

        try:
            response = requests.post(
                NVIDIA_API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": MODEL_NAME,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 1000
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                logger.error(f"NVIDIA API error: {response.status_code} - {response.text}")
                return "I'm having trouble connecting to my AI engine right now. Please try again."
                
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return "Sorry, I encountered an error processing your request."
    
    def extract_action_items(self, context: List[Dict], query: str) -> List[Dict]:
        """Extract action items from context using AI"""
        # This would use another LLM call to parse action items
        # For now, returning extracted actions from context metadata
        actions = []
        
        for doc in context:
            content = doc['content'].lower()
            metadata = doc['metadata']
            
            # Simple heuristic: look for action-oriented language
            if any(word in content for word in ['need to', 'should', 'must', 'todo', 'action item']):
                # Extract potential action
                lines = doc['content'].split('\n')
                for line in lines:
                    if any(word in line.lower() for word in ['need to', 'should', 'must', 'todo', 'action item']):
                        actions.append({
                            "title": line.strip()[:100],
                            "description": line.strip(),
                            "source": metadata.get('source', 'Unknown'),
                            "detected_from": query
                        })
        
        return actions[:5]  # Return top 5
    
    def detect_alerts(self, context: List[Dict]) -> List[Dict]:
        """Detect potential alerts from context"""
        alerts = []
        
        for doc in context:
            content = doc['content'].lower()
            metadata = doc['metadata']
            
            # Critical patterns
            if any(word in content for word in ['blocked', 'critical', 'urgent', 'emergency', 'down']):
                alerts.append({
                    "title": "Critical Blocker Detected",
                    "description": doc['content'][:200] + "...",
                    "priority": "critical",
                    "source": metadata.get('source', 'System'),
                    "detected_at": datetime.now().isoformat()
                })
            
            # Warning patterns
            elif any(word in content for word in ['risk', 'concern', 'delay', 'problem', 'issue']):
                alerts.append({
                    "title": "Potential Risk Identified",
                    "description": doc['content'][:200] + "...",
                    "priority": "warning",
                    "source": metadata.get('source', 'System'),
                    "detected_at": datetime.now().isoformat()
                })
        
        return alerts[:3]  # Return top 3

# Initialize agentic system
agent = AgenticPMCopilot(collection, NVIDIA_API_KEY)


# =========================
# API ENDPOINTS
# =========================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "model": MODEL_NAME,
        "chromadb_docs": collection.count(),
        "actions_count": len(actions_db),
        "alerts_count": len(alerts_db)
    }

@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Main chat endpoint - agentic processing
    """
    try:
        query = request.message
        logger.info(f"Processing query: {query}")
        
        # 1. Classify intent
        intent = agent.classify_intent(query)
        logger.info(f"Detected intent: {intent}")
        
        # 2. Retrieve relevant context
        context = agent.retrieve_context(query, n_results=5)
        logger.info(f"Retrieved {len(context)} context documents")
        
        # 3. Generate response
        response = agent.generate_response(query, context)
        
        # 4. PROACTIVE: Extract action items
        new_actions = agent.extract_action_items(context, query)
        for action_data in new_actions:
            if action_data['title'] not in [a['title'] for a in actions_db]:
                action = {
                    "id": f"action_{len(actions_db) + 1}",
                    "title": action_data['title'],
                    "description": action_data['description'],
                    "assignee": "Unassigned",
                    "due_date": (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d"),
                    "source": action_data['source'],
                    "status": "pending",
                    "priority": "medium",
                    "created_at": datetime.now().isoformat()
                }
                actions_db.append(action)
                logger.info(f"Created action: {action['title']}")
        
        # 5. PROACTIVE: Detect alerts
        new_alerts = agent.detect_alerts(context)
        for alert_data in new_alerts:
            if alert_data['title'] not in [a['title'] for a in alerts_db]:
                alert = {
                    "id": f"alert_{len(alerts_db) + 1}",
                    "title": alert_data['title'],
                    "description": alert_data['description'],
                    "priority": alert_data['priority'],
                    "source": alert_data['source'],
                    "time": datetime.now().strftime("%H:%M"),
                    "created_at": datetime.now().isoformat()
                }
                alerts_db.append(alert)
                logger.info(f"Created alert: {alert['title']} ({alert['priority']})")
        
        return {
            "response": response,
            "intent": intent,
            "context_used": len(context),
            "new_actions": len(new_actions),
            "new_alerts": len(new_alerts)
        }
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/actions")
async def get_actions():
    """Get all action items"""
    return {"actions": actions_db}


@app.post("/actions")
async def create_action(action: ActionCreate):
    """Manually create an action item"""
    new_action = {
        "id": f"action_{len(actions_db) + 1}",
        "title": action.title,
        "description": action.description,
        "assignee": action.assignee,
        "due_date": action.due_date,
        "source": action.source,
        "status": "pending",
        "priority": action.priority,
        "created_at": datetime.now().isoformat()
    }
    actions_db.append(new_action)
    return {"action": new_action}


@app.post("/actions/{action_id}/complete")
async def complete_action(action_id: str):
    """Mark action as completed"""
    for action in actions_db:
        if action['id'] == action_id:
            action['status'] = 'completed'
            action['completed_at'] = datetime.now().isoformat()
            return {"status": "success", "action": action}
    raise HTTPException(status_code=404, detail="Action not found")


@app.post("/actions/{action_id}/snooze")
async def snooze_action(action_id: str):
    """Snooze action for 1 day"""
    for action in actions_db:
        if action['id'] == action_id:
            current_date = datetime.fromisoformat(action['due_date'])
            action['due_date'] = (current_date + timedelta(days=1)).strftime("%Y-%m-%d")
            return {"status": "success", "action": action}
    raise HTTPException(status_code=404, detail="Action not found")


@app.get("/alerts")
async def get_alerts():
    """Get all alerts"""
    # Sort by priority: critical first, then warning, then info
    priority_order = {"critical": 0, "warning": 1, "info": 2}
    sorted_alerts = sorted(alerts_db, key=lambda x: priority_order.get(x['priority'], 3))
    return {"alerts": sorted_alerts}


@app.post("/alerts")
async def create_alert(alert: AlertCreate):
    """Manually create an alert"""
    new_alert = {
        "id": f"alert_{len(alerts_db) + 1}",
        "title": alert.title,
        "description": alert.description,
        "priority": alert.priority,
        "source": alert.source,
        "time": datetime.now().strftime("%H:%M"),
        "created_at": datetime.now().isoformat()
    }
    alerts_db.append(new_alert)
    return {"alert": new_alert}


@app.post("/alerts/{alert_id}/dismiss")
async def dismiss_alert(alert_id: str):
    """Dismiss an alert"""
    global alerts_db
    alerts_db = [a for a in alerts_db if a['id'] != alert_id]
    return {"status": "success"}


@app.post("/sync")
async def sync_data():
    """
    Trigger proactive monitoring and data sync
    This would be called periodically (e.g., every hour) to:
    - Check all data sources
    - Detect new blockers
    - Generate alerts
    - Create action items
    """
    try:
        # In production, this would:
        # 1. Fetch latest data from all sources (Jira, Slack, Meet, etc.)
        # 2. Run analysis on new data
        # 3. Generate alerts for critical issues
        # 4. Create action items for todos
        
        logger.info("Running proactive sync...")
        
        # Example: Check for overdue items
        overdue_actions = [a for a in actions_db if a['status'] == 'pending' 
                          and datetime.fromisoformat(a['due_date']) < datetime.now()]
        
        for action in overdue_actions:
            action['status'] = 'overdue'
            # Create alert for overdue action
            alert = {
                "id": f"alert_{len(alerts_db) + 1}",
                "title": f"Overdue: {action['title']}",
                "description": f"Action item is overdue by {(datetime.now() - datetime.fromisoformat(action['due_date'])).days} days",
                "priority": "warning",
                "source": "System Monitor",
                "time": datetime.now().strftime("%H:%M"),
                "created_at": datetime.now().isoformat()
            }
            alerts_db.append(alert)
        
        return {
            "status": "success",
            "overdue_actions": len(overdue_actions),
            "total_actions": len(actions_db),
            "total_alerts": len(alerts_db)
        }
        
    except Exception as e:
        logger.error(f"Error in sync: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics")
async def get_analytics():
    """
    Get analytics and insights
    """
    total_actions = len(actions_db)
    pending_actions = len([a for a in actions_db if a['status'] == 'pending'])
    completed_actions = len([a for a in actions_db if a['status'] == 'completed'])
    overdue_actions = len([a for a in actions_db if a['status'] == 'overdue'])
    
    critical_alerts = len([a for a in alerts_db if a['priority'] == 'critical'])
    warning_alerts = len([a for a in alerts_db if a['priority'] == 'warning'])
    
    return {
        "actions": {
            "total": total_actions,
            "pending": pending_actions,
            "completed": completed_actions,
            "overdue": overdue_actions,
            "completion_rate": f"{(completed_actions/total_actions*100) if total_actions > 0 else 0:.1f}%"
        },
        "alerts": {
            "total": len(alerts_db),
            "critical": critical_alerts,
            "warning": warning_alerts
        },
        "health_score": max(0, 100 - (overdue_actions * 10) - (critical_alerts * 15))
    }


@app.post("/add-batch")
async def add_batch(req: Request):
    """Add multiple documents to ChromaDB (for demo data loading)"""
    try:
        data = await req.json()
        documents = data.get("documents", [])
        
        if not documents:
            raise HTTPException(status_code=400, detail="Documents required")
        
        contents = []
        metadatas = []
        ids = []
        
        import uuid
        for doc in documents:
            content = doc.get("content")
            if not content:
                continue
                
            contents.append(content)
            metadatas.append(doc.get("metadata", {}))
            ids.append(doc.get("id", str(uuid.uuid4())))
        
        collection.add(
            documents=contents,
            metadatas=metadatas,
            ids=ids
        )
        
        logger.info(f"Added {len(contents)} documents to ChromaDB")
        
        return {
            "status": "success",
            "count": len(contents),
            "message": f"Added {len(contents)} documents"
        }
        
    except Exception as e:
        logger.error(f"Error adding batch: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
async def status():
    """Get server status (alias for root endpoint)"""
    return {
        "status": "running",
        "model": MODEL_NAME,
        "chromadb_docs": collection.count(),
        "actions_count": len(actions_db),
        "alerts_count": len(alerts_db)
    }


# =========================
# MEETINGS & ANALYTICS DATA
# =========================

# Mock meetings database
meetings_db = [
    {
        "id": "meeting_001",
        "title": "Sprint 24 Planning",
        "date": "Today",
        "time": "10:00 AM",
        "duration": 45,
        "status": "upcoming",
        "attendees": ["Sarah", "Mike", "Tom", "Jessica", "You"],
        "brief": {
            "context": [
                "Sprint 23 completed 72/80 points (90%)",
                "PAY-567 critical - needs decision today",
                "Tom blocked on design for 5 days",
                "Team velocity trending down 8%"
            ],
            "decisions_needed": [
                "Approve Mike's payment hotfix deployment",
                "Resolve Tom's design blocker",
                "Descope or extend sprint (8 points at risk)"
            ],
            "blockers": [
                "Design review taking too long",
                "Staging environment unstable",
                "Third-party API docs delayed"
            ]
        }
    },
    {
        "id": "meeting_002",
        "title": "Daily Standup",
        "date": "Today",
        "time": "9:30 AM",
        "duration": 15,
        "status": "completed",
        "attendees": ["Sarah", "Mike", "Tom", "Jessica"],
        "summary": {
            "key_decisions": [
                "Mike to deploy payment fix by EOD",
                "Sarah to escalate design blocker"
            ],
            "action_items": [
                "Mike: Deploy PAY-567 hotfix by 5 PM",
                "Sarah: Schedule design sync meeting",
                "Tom: Document API integration issues"
            ],
            "blockers": [
                "Tom waiting on design feedback (5 days)",
                "Staging environment down"
            ],
            "next_steps": [
                "Follow up on design review SLA",
                "Monitor payment fix deployment"
            ]
        }
    },
    {
        "id": "meeting_003",
        "title": "Q1 Product Review",
        "date": "Tomorrow",
        "time": "2:00 PM",
        "duration": 60,
        "status": "upcoming",
        "attendees": ["Leadership", "Product Team", "Engineering Leads"],
        "brief": {
            "context": [
                "Q1 roadmap 78% complete",
                "Auth system on track for end of Jan",
                "Payment improvements deployed",
                "Mobile MVP pushed to Feb"
            ],
            "decisions_needed": [
                "Approve Q2 roadmap priorities",
                "Allocate resources for mobile push",
                "Decision on API v2 timeline"
            ],
            "blockers": []
        }
    }
]

# Mock analytics data
analytics_data = {
    "health_score": 78,
    "change": -5,
    "customer": {
        "nps": 42,
        "nps_change": -8,
        "support_tickets": 156,
        "tickets_change": 23
    },
    "tech": {
        "uptime": 99.5,
        "errors_critical": 23,
        "errors_change": 40
    },
    "team": {
        "velocity": 72,
        "velocity_change": -8,
        "burnout_risk": "Low"
    },
    "alerts": [
        {
            "severity": "critical",
            "title": "Payment Error Spike",
            "description": "Payment errors up 40% in last 24 hours. Correlates with customer sentiment drop."
        },
        {
            "severity": "warning",
            "title": "Support Ticket Volume Increase",
            "description": "Support tickets up 23% this week, mostly payment-related inquiries."
        }
    ],
    "insights": [
        {
            "title": "Payment Issue Impacting Customer Satisfaction",
            "description": "The payment error spike (PAY-567) is directly correlated with the 8-point NPS drop. Error rate jumped from 0.5% to 3% after v2.3 deployment.",
            "recommendation": "Deploy Mike's tested hotfix immediately. This should resolve both the error rate and prevent further NPS decline. Estimated recovery: 48 hours."
        },
        {
            "title": "Team Velocity Declining",
            "description": "Sprint velocity down 8% over last 3 sprints. Primary factors: design bottleneck (35% of delays) and staging environment issues (25% of delays).",
            "recommendation": "Implement design review SLA (48 hours max) and prioritize staging stability. Expected velocity improvement: 12-15%."
        },
        {
            "title": "Proactive Customer Outreach Needed",
            "description": "With payment issues affecting 3% of transactions and NPS declining, at-risk customer segment identified (156 users experienced failures).",
            "recommendation": "Launch proactive email campaign to affected customers explaining the issue and resolution. Include service credit offer for critical accounts."
        }
    ],
    "trends": {
        "velocity": {
            "labels": ["Sprint 19", "Sprint 20", "Sprint 21", "Sprint 22", "Sprint 23", "Sprint 24"],
            "values": [75, 78, 72, 68, 72, 66]
        },
        "nps": {
            "labels": ["Week 1", "Week 2", "Week 3", "Week 4"],
            "values": [52, 50, 48, 42]
        }
    }
}


# =========================
# MEETINGS ENDPOINTS
# =========================

@app.get("/meetings")
async def get_meetings():
    """Get all meetings"""
    return {"meetings": meetings_db}


@app.get("/meetings/upcoming")
async def get_upcoming_meetings():
    """Get upcoming meetings with auto-generated briefs"""
    upcoming = [m for m in meetings_db if m['status'] == 'upcoming']
    return {"meetings": upcoming}


@app.get("/meetings/{meeting_id}")
async def get_meeting(meeting_id: str):
    """Get specific meeting details"""
    meeting = next((m for m in meetings_db if m['id'] == meeting_id), None)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return {"meeting": meeting}


@app.post("/meetings/{meeting_id}/start")
async def start_meeting(meeting_id: str):
    """Start a meeting (activate live mode)"""
    for meeting in meetings_db:
        if meeting['id'] == meeting_id:
            meeting['status'] = 'live'
            meeting['live_data'] = {
                "elapsed_time": 0,
                "decisions": [],
                "action_items": []
            }
            logger.info(f"Started meeting: {meeting['title']}")
            return {"status": "success", "meeting": meeting}
    raise HTTPException(status_code=404, detail="Meeting not found")


@app.post("/meetings/{meeting_id}/end")
async def end_meeting(meeting_id: str):
    """End meeting and generate summary"""
    for meeting in meetings_db:
        if meeting['id'] == meeting_id:
            meeting['status'] = 'completed'
            # In production, this would use LLM to generate summary
            meeting['summary'] = {
                "key_decisions": [
                    "Approved payment gateway hotfix deployment",
                    "Established design review SLA (48 hours)"
                ],
                "action_items": [
                    "Mike to deploy fix by EOD",
                    "Sarah to implement design review process"
                ],
                "blockers": [
                    "Design bandwidth constraint"
                ],
                "next_steps": [
                    "Monitor payment metrics post-deployment",
                    "Schedule design capacity review"
                ]
            }
            logger.info(f"Ended meeting: {meeting['title']}")
            return {"status": "success", "meeting": meeting}
    raise HTTPException(status_code=404, detail="Meeting not found")


@app.get("/meetings/{meeting_id}/brief")
async def get_meeting_brief(meeting_id: str):
    """Get pre-meeting brief"""
    meeting = next((m for m in meetings_db if m['id'] == meeting_id), None)
    if not meeting or 'brief' not in meeting:
        raise HTTPException(status_code=404, detail="Brief not available")
    return {"brief": meeting['brief']}


@app.get("/meetings/{meeting_id}/summary")
async def get_meeting_summary(meeting_id: str):
    """Get post-meeting summary"""
    meeting = next((m for m in meetings_db if m['id'] == meeting_id), None)
    if not meeting or 'summary' not in meeting:
        raise HTTPException(status_code=404, detail="Summary not available")
    return {"summary": meeting['summary']}


# =========================
# ANALYTICS ENDPOINTS
# =========================

@app.get("/analytics/dashboard")
async def get_analytics_dashboard():
    """Get complete analytics dashboard data"""
    return analytics_data


@app.get("/analytics/health-score")
async def get_health_score():
    """Get overall product health score"""
    return {
        "score": analytics_data['health_score'],
        "change": analytics_data['change']
    }


@app.get("/analytics/customer")
async def get_customer_metrics():
    """Get customer-focused metrics"""
    return {"customer": analytics_data['customer']}


@app.get("/analytics/tech")
async def get_tech_metrics():
    """Get technical health metrics"""
    return {"tech": analytics_data['tech']}


@app.get("/analytics/team")
async def get_team_metrics():
    """Get team performance metrics"""
    return {"team": analytics_data['team']}


@app.get("/analytics/trends")
async def get_trends():
    """Get trend data for charts"""
    return {"trends": analytics_data['trends']}


@app.get("/analytics/insights")
async def get_insights():
    """Get AI-generated insights"""
    return {"insights": analytics_data['insights']}


if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("🚀 PM Copilot - Full Suite Server Starting...")
    print("=" * 60)
    print(f"📊 ChromaDB Documents: {collection.count()}")
    print(f"✅ Actions Loaded: {len(actions_db)}")
    print(f"🔔 Alerts Loaded: {len(alerts_db)}")
    print(f"📅 Meetings Loaded: {len(meetings_db)}")
    print(f"📈 Analytics: Health Score {analytics_data['health_score']}/100")
    print("=" * 60)
    print("🌐 Server running at: http://localhost:8000")
    print("📖 API Docs: http://localhost:8000/docs")
    print("=" * 60)
    print("\n✨ New Features Available:")
    print("   • Meetings tab with auto-briefs & summaries")
    print("   • Analytics dashboard with health score")
    print("   • AI-powered insights & recommendations")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
