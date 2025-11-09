"""
Load demo PM data into ChromaDB
"""

import requests
import json

SERVER_URL = "http://127.0.0.1:8000"

# Sample PM documents
demo_docs = [
    {
        "content": """Sprint 24 Planning Meeting - January 22, 2024

Goals:
- Complete user authentication feature (AUTH-234)
- Fix payment gateway timeout issues (PAY-567)
- Update API documentation

Team Capacity: 80 story points
Committed: 75 story points

Blockers Identified:
- Mike: Waiting on payment gateway API documentation
- Tom: Blocked on design feedback for dashboard UI
- Sarah: Third-party auth provider docs delayed

Decisions Made:
- Prioritize payment gateway fix as critical (affecting revenue)
- Establish design review SLA - 48 hours max
- Schedule bi-weekly design sync meetings
- Add buffer time for API integration tasks""",
        "metadata": {
            "source": "google_meet",
            "type": "sprint_planning",
            "date": "2024-01-22"
        }
    },
    {
        "content": """Daily Standup - January 23, 2024

Sarah: Completed login flow, starting password reset feature
Mike: Found payment timeout bug, fix ready but needs PM approval for hotfix
Tom: Still blocked on design feedback, 3 days now
Jessica: API documentation 60% complete, on track

Blockers:
- Tom waiting on design team (3 days)
- Mike needs hotfix approval for production
- Staging environment down (infrastructure issue)

Action Items:
- Sarah to follow up with design team TODAY
- PM to approve Mike's hotfix deployment
- DevOps to investigate staging stability""",
        "metadata": {
            "source": "google_meet",
            "type": "standup",
            "date": "2024-01-23"
        }
    },
    {
        "content": """Jira Issue: AUTH-234
Summary: Implement OAuth2 password reset flow
Status: In Progress
Priority: High
Assignee: Sarah Chen
Story Points: 13
Sprint: Sprint 24

Description:
Users need ability to reset password through OAuth2 flow. Must integrate with existing auth system and send email notifications.

Recent Comments:
- Mike (Jan 22): Blocked on third-party API documentation. Expected Wednesday.
- Sarah (Jan 23): Started implementation, email templates ready
- Product (Jan 23): This is critical for user retention""",
        "metadata": {
            "source": "jira",
            "type": "issue",
            "issue_key": "AUTH-234",
            "status": "In Progress",
            "priority": "High"
        }
    },
    {
        "content": """Jira Issue: PAY-567
Summary: Fix payment gateway timeout configuration
Status: Ready for Deploy
Priority: Critical
Assignee: Mike Johnson
Story Points: 3

Description:
URGENT: 3% of payment transactions failing due to timeout misconfiguration in v2.3 deployment. Losing ~$500/hour in revenue.

Root Cause: Timeout set to 5s, should be 30s based on provider recommendations.

Solution: Configuration change ready, tested on staging with 1000 transactions - 0% failure rate.

Needs: PM approval for hotfix deployment to production""",
        "metadata": {
            "source": "jira",
            "type": "issue",
            "issue_key": "PAY-567",
            "status": "Ready for Deploy",
            "priority": "Critical"
        }
    },
    {
        "content": """Slack #team-backend - January 23, 2024

Mike: @sarah The staging environment is down again. This is the third time this week. We need to prioritize infrastructure stability.
[+1 reactions from 5 team members]

Tom: FYI - design team pushed back the dashboard mockups to next week. @mike this means you're blocked on that UI work we discussed.

Sarah: Sprint velocity update: We're tracking at 68/80 points with 3 days left. AUTH-234 and PAY-567 are at risk. Should we descope or push?

Mike: Let's descope AUTH-234 to Sprint 25. It's not blocking anything. Keep PAY-567 as critical - that's customer-facing and losing revenue.

Jessica: Quick win - I found the issue with the payment timeout. It's a config problem from the last deployment. I have a fix ready but need PM approval for hotfix to prod.""",
        "metadata": {
            "source": "slack",
            "type": "team_discussion",
            "channel": "team-backend",
            "date": "2024-01-23"
        }
    },
    {
        "content": """Sprint 23 Retrospective - January 19, 2024

What Went Well:
- Completed all critical security fixes
- Great collaboration on payment system
- Improved test coverage to 85%
- Good communication in daily standups

What Could Improve:
- Too many interruptions for urgent bugs (broke focus time)
- Need better estimation for API integration work
- Design feedback loop too slow (blocking developers)
- Staging environment instability causing delays

Action Items:
1. Establish "focus time" blocks for developers (Sarah) - Due: Jan 22
2. Create design review SLA - 24-48 hours (Sarah) - Due: Jan 22
3. Schedule bi-weekly design sync meetings (Sarah) - Due: Jan 25
4. Add 20% buffer time for API integration tasks (Team) - Start: Sprint 24
5. Investigate staging environment root cause (DevOps) - Due: Jan 26""",
        "metadata": {
            "source": "google_meet",
            "type": "retrospective",
            "sprint": "Sprint 23",
            "date": "2024-01-19"
        }
    },
    {
        "content": """Q1 2024 Product Roadmap

Priority 1 (Must Have):
- User authentication & authorization system (Sprint 24-25)
- Payment processing improvements (Sprint 24)
- Mobile app MVP (Sprint 26-28)
- API v2 launch (Sprint 29)

Priority 2 (Should Have):
- Analytics dashboard (Sprint 27)
- Admin panel enhancements (Sprint 26)
- Email notification system (Sprint 25)

Key Milestones:
- End of Jan: Auth system complete
- Mid Feb: Payment system stable
- End Feb: Mobile MVP beta
- End Mar: API v2 public launch

Current Blockers:
- Payment gateway documentation delayed
- Design bandwidth constrained
- Infrastructure stability issues""",
        "metadata": {
            "source": "product",
            "type": "roadmap",
            "quarter": "Q1 2024"
        }
    },
    {
        "content": """GitHub PR #345: Fix payment gateway timeout
Author: Mike Johnson
Status: Open
Labels: bug, hotfix, payments, critical

Description:
Fixes 3% transaction failure rate due to timeout misconfiguration in v2.3

Changes:
- Increased payment gateway timeout from 5s to 30s
- Updated config documentation
- Added timeout monitoring

Testing:
- Tested on staging with 1000 transactions
- 0% failure rate
- Average response time: 8.2s

Impact:
- Resolves PAY-567
- Revenue impact: ~$500/hour in failed transactions
- Should be deployed as HOTFIX

Waiting for: PM approval for production deployment""",
        "metadata": {
            "source": "github",
            "type": "pull_request",
            "pr_number": 345,
            "author": "Mike Johnson"
        }
    }
]

def load_demo_data():
    """Load all demo documents"""
    print("=" * 60)
    print("📚 Loading PM demo data...")
    print("=" * 60)
    
    # Check server
    try:
        response = requests.get(f"{SERVER_URL}/status")
        print(f"✅ Server running: {response.json()}")
    except:
        print("❌ Server not running! Start it first:")
        print("   python local_server.py")
        return
    
    # Add documents
    try:
        response = requests.post(
            f"{SERVER_URL}/add-batch",
            json={"documents": demo_docs}
        )
        
        if response.ok:
            result = response.json()
            print(f"\n✅ Loaded {result['count']} documents!")
        else:
            print(f"❌ Failed: {response.text}")
            return
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return
    
    # Show status
    response = requests.get(f"{SERVER_URL}/status")
    if response.ok:
        info = response.json()
        print(f"\n📊 Total documents: {info['chromadb_docs']}")
    
    print("\n" + "=" * 60)
    print("✅ Demo data ready!")
    print("=" * 60)
    print("\nTry asking:")
    print("  • What blockers were mentioned this week?")
    print("  • What's the status of the payment gateway issue?")
    print("  • What action items came from the retrospective?")
    print("  • Show me critical Jira tickets")
    print("  • What was decided in sprint planning?")
    print("=" * 60)

if __name__ == "__main__":
    load_demo_data()