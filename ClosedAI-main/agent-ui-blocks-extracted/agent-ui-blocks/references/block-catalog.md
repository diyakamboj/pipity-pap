# Block catalog

Full prop schema (as example payloads) for every block type in the pack, grouped by category. Each example is a complete `props` object — copy the shape, swap in real data. All blocks also accept the shared customization props described in SKILL.md (`tone`, `size`, `align` where applicable).


## People (`people`)

### `employee-card-compact`

```ui-block
{
  "type": "employee-card-compact",
  "version": 1,
  "props": {
    "name": "Priya Nair",
    "role": "Staff Engineer",
    "status": "active"
  }
}
```

### `employee-card-detailed`

```ui-block
{
  "type": "employee-card-detailed",
  "version": 1,
  "props": {
    "name": "Priya Nair",
    "role": "Staff Engineer",
    "team": "Platform",
    "status": "active",
    "email": "priya@company.com",
    "tenure": "3.5 yrs",
    "projects": 4
  }
}
```

### `employee-card-availability`

```ui-block
{
  "type": "employee-card-availability",
  "version": 1,
  "props": {
    "name": "Marcus Webb",
    "role": "SDET",
    "week": [
      {
        "day": "Mon",
        "free": true
      },
      {
        "day": "Tue",
        "free": false
      },
      {
        "day": "Wed",
        "free": true
      },
      {
        "day": "Thu",
        "free": true
      },
      {
        "day": "Fri",
        "free": false
      }
    ]
  }
}
```

### `employee-card-contact`

```ui-block
{
  "type": "employee-card-contact",
  "version": 1,
  "props": {
    "name": "Ana Torres",
    "role": "Product Manager",
    "email": "ana@company.com",
    "phone": "+1 (206) 555-0192",
    "status": "away"
  }
}
```

### `employee-card-stats`

```ui-block
{
  "type": "employee-card-stats",
  "version": 1,
  "props": {
    "name": "Priya Nair",
    "role": "Staff Engineer",
    "stats": [
      {
        "label": "PRs",
        "value": 214
      },
      {
        "label": "Reviews",
        "value": 88
      },
      {
        "label": "Reports",
        "value": 3
      }
    ]
  }
}
```

### `team-roster`

```ui-block
{
  "type": "team-roster",
  "version": 1,
  "props": {
    "title": "Test Intelligence squad",
    "members": [
      {
        "name": "Priya Nair",
        "role": "Staff Engineer",
        "status": "active"
      },
      {
        "name": "Marcus Webb",
        "role": "SDET",
        "status": "away"
      },
      {
        "name": "Ana Torres",
        "role": "PM",
        "status": "pto"
      }
    ]
  }
}
```

### `org-node`

```ui-block
{
  "type": "org-node",
  "version": 1,
  "props": {
    "manager": {
      "name": "Priya Nair",
      "role": "Staff Engineer"
    },
    "reports": [
      {
        "name": "Jae Kim",
        "role": "SDE II"
      },
      {
        "name": "Lucia Ferrer",
        "role": "SDE II"
      }
    ]
  }
}
```


## Data & charts (`data`)

### `stat-grid`

```ui-block
{
  "type": "stat-grid",
  "version": 1,
  "props": {
    "title": "This week",
    "stats": [
      {
        "label": "Tests run",
        "value": "4,812",
        "delta": "+6%",
        "trend": "up"
      },
      {
        "label": "Flaky rate",
        "value": "1.2%",
        "delta": "-0.3%",
        "trend": "down"
      },
      {
        "label": "Avg duration",
        "value": "8m 40s",
        "delta": "+40s",
        "trend": "up"
      },
      {
        "label": "Coverage",
        "value": "78%",
        "delta": "flat",
        "trend": "flat"
      }
    ]
  }
}
```

### `stat-hero`

```ui-block
{
  "type": "stat-hero",
  "version": 1,
  "props": {
    "label": "Tests run this week",
    "value": "4,812",
    "delta": "+6% vs last week",
    "trend": "up",
    "context": "Across 6 shards"
  }
}
```

### `bar-chart`

```ui-block
{
  "type": "bar-chart",
  "version": 1,
  "props": {
    "title": "Failures by shard",
    "unit": "",
    "data": [
      {
        "label": "Shard 1",
        "value": 2
      },
      {
        "label": "Shard 2",
        "value": 0
      },
      {
        "label": "Shard 3",
        "value": 5
      },
      {
        "label": "Shard 4",
        "value": 1
      }
    ]
  }
}
```

### `horizontal-bar-chart`

```ui-block
{
  "type": "horizontal-bar-chart",
  "version": 1,
  "props": {
    "title": "Top flaky tests",
    "unit": "x",
    "data": [
      {
        "label": "checkout.spec",
        "value": 9
      },
      {
        "label": "login.spec",
        "value": 5
      },
      {
        "label": "search.spec",
        "value": 3
      }
    ]
  }
}
```

### `line-chart`

```ui-block
{
  "type": "line-chart",
  "version": 1,
  "props": {
    "title": "Flaky test rate",
    "unit": "%",
    "data": [
      {
        "x": "Mon",
        "value": 2.1
      },
      {
        "x": "Tue",
        "value": 1.8
      },
      {
        "x": "Wed",
        "value": 2.4
      },
      {
        "x": "Thu",
        "value": 1.2
      },
      {
        "x": "Fri",
        "value": 0.9
      }
    ]
  }
}
```

### `area-chart`

```ui-block
{
  "type": "area-chart",
  "version": 1,
  "props": {
    "title": "Test suite growth",
    "unit": "",
    "data": [
      {
        "x": "Jan",
        "value": 1200
      },
      {
        "x": "Feb",
        "value": 1450
      },
      {
        "x": "Mar",
        "value": 1600
      },
      {
        "x": "Apr",
        "value": 2100
      }
    ]
  }
}
```

### `donut-chart`

```ui-block
{
  "type": "donut-chart",
  "version": 1,
  "props": {
    "title": "Failure categories",
    "data": [
      {
        "label": "Timing",
        "value": 42
      },
      {
        "label": "Assertion",
        "value": 28
      },
      {
        "label": "Environment",
        "value": 18
      },
      {
        "label": "Unknown",
        "value": 12
      }
    ]
  }
}
```

### `gauge`

```ui-block
{
  "type": "gauge",
  "version": 1,
  "props": {
    "label": "CPU utilization",
    "value": 72,
    "max": 100,
    "unit": "%"
  }
}
```


## Workflow (`workflow`)

### `stepper`

```ui-block
{
  "type": "stepper",
  "version": 1,
  "props": {
    "title": "Deploy pipeline",
    "steps": [
      {
        "label": "Build",
        "status": "done"
      },
      {
        "label": "Test",
        "status": "active"
      },
      {
        "label": "Deploy",
        "status": "pending"
      }
    ]
  }
}
```

### `stepper-horizontal`

```ui-block
{
  "type": "stepper-horizontal",
  "version": 1,
  "props": {
    "steps": [
      {
        "label": "Draft",
        "status": "done"
      },
      {
        "label": "Review",
        "status": "active"
      },
      {
        "label": "Publish",
        "status": "pending"
      }
    ]
  }
}
```

### `approval`

```ui-block
{
  "type": "approval",
  "version": 1,
  "props": {
    "title": "Merge auto-fix",
    "description": "Agent proposed a fix with 94% confidence.",
    "requestor": "AI Test Intelligence pipeline",
    "actions": [
      {
        "label": "Approve",
        "style": "primary"
      },
      {
        "label": "Reject",
        "style": "secondary"
      }
    ]
  }
}
```

### `approval-compact`

```ui-block
{
  "type": "approval-compact",
  "version": 1,
  "props": {
    "title": "Merge accessibility fix #221",
    "requestor": "Accessibility Plugin"
  }
}
```

### `timeline`

```ui-block
{
  "type": "timeline",
  "version": 1,
  "props": {
    "title": "Incident timeline",
    "events": [
      {
        "label": "Alert fired",
        "date": "09:14",
        "status": "done"
      },
      {
        "label": "RCA generated",
        "date": "09:16",
        "status": "done"
      },
      {
        "label": "Fix under review",
        "date": "09:22",
        "status": "active"
      },
      {
        "label": "Deploy",
        "date": "pending",
        "status": "pending"
      }
    ]
  }
}
```

### `progress-bar`

```ui-block
{
  "type": "progress-bar",
  "version": 1,
  "props": {
    "label": "Chapter revisions",
    "value": 9,
    "max": 14,
    "unit": " ch"
  }
}
```


## Communication & content (`content`)

### `email`

```ui-block
{
  "type": "email",
  "version": 1,
  "props": {
    "to": "alvin@publisher.com",
    "subject": "Re: Chapter 9 revisions",
    "body": "Incorporated the agentic workflow feedback, kept edits minimal.",
    "actions": [
      "send",
      "discard"
    ]
  }
}
```

### `chat-thread`

```ui-block
{
  "type": "chat-thread",
  "version": 1,
  "props": {
    "messages": [
      {
        "sender": "Marcus Webb",
        "message": "Shard 3 flake looks like a real race condition.",
        "time": "10:42"
      },
      {
        "sender": "Priya Nair",
        "message": "Agreed \u2014 pulling in the RCA output now.",
        "time": "10:44"
      }
    ]
  }
}
```

### `alert-banner`

```ui-block
{
  "type": "alert-banner",
  "version": 1,
  "props": {
    "level": "warning",
    "title": "Coverage dropped below threshold",
    "message": "Dataverse CRM module fell to 71%, below the 75% gate."
  }
}
```

### `table`

```ui-block
{
  "type": "table",
  "version": 1,
  "props": {
    "title": "Shard results",
    "columns": [
      "Shard",
      "Tests",
      "Status"
    ],
    "rows": [
      [
        "1",
        "142",
        "passed"
      ],
      [
        "2",
        "138",
        "passed"
      ],
      [
        "3",
        "140",
        "1 flaky"
      ]
    ]
  }
}
```

### `quote`

```ui-block
{
  "type": "quote",
  "version": 1,
  "props": {
    "text": "Production-honest framing beats a vendor pitch every time.",
    "author": "Deepak",
    "role": "Engineering Systems"
  }
}
```

### `code-snippet`

```ui-block
{
  "type": "code-snippet",
  "version": 1,
  "props": {
    "text": "Production-honest framing beats a vendor pitch every time.",
    "author": "Deepak",
    "role": "Engineering Systems"
  }
}
```

### `badge-list`

```ui-block
{
  "type": "badge-list",
  "version": 1,
  "props": {
    "title": "Tags",
    "badges": [
      {
        "label": "flaky",
        "tone": "warning"
      },
      {
        "label": "p1",
        "tone": "violet"
      },
      {
        "label": "triaged",
        "tone": "success"
      }
    ]
  }
}
```

### `rating`

```ui-block
{
  "type": "rating",
  "version": 1,
  "props": {
    "label": "Reviewer confidence",
    "value": 4,
    "max": 5
  }
}
```

### `file-attachment`

```ui-block
{
  "type": "file-attachment",
  "version": 1,
  "props": {
    "filename": "chapter-9-revised.docx",
    "size": "412 KB",
    "kind": "docx"
  }
}
```

### `calendar-event`

```ui-block
{
  "type": "calendar-event",
  "version": 1,
  "props": {
    "title": "Sprint planning",
    "time": "Tue 10:00 \u2013 10:45 AM",
    "location": "Teams",
    "attendees": 6
  }
}
```

### `avatar-group`

```ui-block
{
  "type": "avatar-group",
  "version": 1,
  "props": {
    "title": "Reviewers",
    "names": [
      "Priya Nair",
      "Marcus Webb",
      "Ana Torres"
    ],
    "overflow": 2
  }
}
```


## Forms & input (`forms`)

### `form-field-group`

```ui-block
{
  "type": "form-field-group",
  "version": 1,
  "props": {
    "title": "Submitted details",
    "fields": [
      {
        "label": "Preferred start date",
        "value": "Sept 2"
      },
      {
        "label": "Manager",
        "value": "Priya Nair"
      },
      {
        "label": "Notes",
        "value": ""
      }
    ]
  }
}
```

### `survey-poll`

```ui-block
{
  "type": "survey-poll",
  "version": 1,
  "props": {
    "question": "Preferred meeting format?",
    "options": [
      {
        "label": "In person",
        "votes": 12
      },
      {
        "label": "Video call",
        "votes": 28
      },
      {
        "label": "Async doc",
        "votes": 7
      }
    ]
  }
}
```

### `signature-block`

```ui-block
{
  "type": "signature-block",
  "version": 1,
  "props": {
    "name": "Deepak",
    "role": "Requestor",
    "status": "signed",
    "date": "Aug 12"
  }
}
```

### `toggle-settings`

```ui-block
{
  "type": "toggle-settings",
  "version": 1,
  "props": {
    "title": "Notification preferences",
    "settings": [
      {
        "label": "Email digest",
        "on": true
      },
      {
        "label": "Slack DMs",
        "on": false
      },
      {
        "label": "Weekly summary",
        "on": true
      }
    ]
  }
}
```


## Directory & documents (`directory`)

### `document-preview`

```ui-block
{
  "type": "document-preview",
  "version": 1,
  "props": {
    "title": "Production-Grade AI Engineering \u2014 outline",
    "pages": 14,
    "status": "draft",
    "kind": "docx"
  }
}
```

### `directory-search-result`

```ui-block
{
  "type": "directory-search-result",
  "version": 1,
  "props": {
    "query": "platform engineering",
    "results": [
      {
        "name": "Priya Nair",
        "role": "Staff Engineer",
        "location": "Redmond"
      },
      {
        "name": "Jae Kim",
        "role": "SDE II",
        "location": "Remote"
      }
    ]
  }
}
```

### `faq-expandable`

```ui-block
{
  "type": "faq-expandable",
  "version": 1,
  "props": {
    "items": [
      {
        "question": "How is the shard count chosen?",
        "answer": "Based on historical duration data, rebalanced weekly."
      },
      {
        "question": "What counts as flaky?",
        "answer": "Any test failing on retry with no code change."
      }
    ]
  }
}
```

### `key-value-list`

```ui-block
{
  "type": "key-value-list",
  "version": 1,
  "props": {
    "title": "Build details",
    "pairs": [
      {
        "key": "Branch",
        "value": "main"
      },
      {
        "key": "Commit",
        "value": "a3f9c12"
      },
      {
        "key": "Duration",
        "value": "8m 40s"
      }
    ]
  }
}
```


## Metrics & comparison (`metrics`)

### `balance-meter`

```ui-block
{
  "type": "balance-meter",
  "version": 1,
  "props": {
    "label": "Storage used",
    "used": 42,
    "total": 100,
    "unit": " GB",
    "tone": "teal"
  }
}
```

### `amount-breakdown`

```ui-block
{
  "type": "amount-breakdown",
  "version": 1,
  "props": {
    "title": "Monthly cloud spend",
    "total": "4,210",
    "currency": "$",
    "items": [
      {
        "label": "Compute",
        "amount": "2,800"
      },
      {
        "label": "Storage",
        "amount": "740"
      },
      {
        "label": "Networking",
        "amount": "670"
      }
    ]
  }
}
```

### `comparison-two-column`

```ui-block
{
  "type": "comparison-two-column",
  "version": 1,
  "props": {
    "left": {
      "title": "Before",
      "rows": [
        "Manual triage",
        "4hr avg RCA",
        "No auto-PR"
      ]
    },
    "right": {
      "title": "After",
      "rows": [
        "Auto-classified",
        "12min avg RCA",
        "PR drafted"
      ]
    }
  }
}
```

### `milestone-tracker`

```ui-block
{
  "type": "milestone-tracker",
  "version": 1,
  "props": {
    "title": "Book manuscript",
    "milestones": [
      {
        "label": "Outline",
        "done": true
      },
      {
        "label": "Draft",
        "done": true
      },
      {
        "label": "Review",
        "done": false
      },
      {
        "label": "Final",
        "done": false
      }
    ]
  }
}
```

### `metric-comparison`

```ui-block
{
  "type": "metric-comparison",
  "version": 1,
  "props": {
    "metrics": [
      {
        "label": "This week",
        "value": "4,812"
      },
      {
        "label": "Last week",
        "value": "4,530"
      },
      {
        "label": "4wk avg",
        "value": "4,690"
      }
    ]
  }
}
```


## General purpose (`general`)

### `summary-card`

```ui-block
{
  "type": "summary-card",
  "version": 1,
  "props": {
    "title": "Ready for review",
    "body": "The accessibility plugin's before/after metrics are compiled and ready for the exec summary.",
    "tone": "teal",
    "footer": "Updated 2 min ago"
  }
}
```

### `task-card`

```ui-block
{
  "type": "task-card",
  "version": 1,
  "props": {
    "title": "Write chapter 12 instrumentation section",
    "tag": "book",
    "assignee": "Deepak",
    "due": "Fri",
    "tone": "violet"
  }
}
```

### `comment-thread`

```ui-block
{
  "type": "comment-thread",
  "version": 1,
  "props": {
    "comments": [
      {
        "author": "Stephanie",
        "text": "Can we tighten the intro to chapter 9?",
        "time": "Mon"
      },
      {
        "author": "Deepak",
        "text": "Agreed, trimming now.",
        "time": "Mon",
        "depth": 1
      }
    ]
  }
}
```

    ]
  }
}
```

### `stat-strip`

```ui-block
{
  "type": "stat-strip",
  "version": 1,
  "props": {
    "title": "Sprint snapshot",
    "stats": [
      {
        "label": "open",
        "value": 12,
        "tone": "amber"
      },
      {
        "label": "in review",
        "value": 4,
        "tone": "blue"
      },
      {
        "label": "blocked",
        "value": 1,
        "tone": "red"
      }
    ]
  }
}
```

### `icon-list`

```ui-block
{
  "type": "icon-list",
  "version": 1,
  "props": {
    "title": "What's next",
    "tone": "teal",
    "items": [
      {
        "icon": "mail",
        "label": "Send revised outline to Alvin",
        "description": "Draft is ready in the shared folder"
      },
      {
        "icon": "calendar",
        "label": "Confirm chapter 13 deadline"
      },
      {
        "icon": "star",
        "label": "Flag chapter 9 for a second review",
        "tone": "amber"
      }
    ]
  }
}
```

### `link-preview`

```ui-block
{
  "type": "link-preview",
  "version": 1,
  "props": {
    "title": "Production-Grade AI Engineering \u2014 style guide",
    "domain": "docs.company.com",
    "description": "Shared conventions for tone, terminology, and formatting across chapters.",
    "tone": "violet"
  }
}
```

### `accordion`

```ui-block
{
  "type": "accordion",
  "version": 1,
  "props": {
    "title": "Open questions",
    "defaultOpen": 0,
    "items": [
      {
        "title": "How is the shard count chosen?",
        "body": "Based on historical duration data, rebalanced weekly."
      },
      {
        "title": "What counts as flaky?",
        "body": "Any test failing on retry with no code change."
      }
    ]
  }
}
```

### `tag-cloud`

```ui-block
{
  "type": "tag-cloud",
  "version": 1,
  "props": {
    "title": "Themes in this chapter",
    "size": "comfortable",
    "tags": [
      {
        "label": "instrumentation",
        "tone": "violet"
      },
      {
        "label": "observability",
        "tone": "teal"
      },
      {
        "label": "draft",
        "tone": "amber"
      },
      {
        "label": "priority",
        "tone": "#e11d48"
      }
    ]
  }
}
```

### `empty-state`

```ui-block
{
  "type": "empty-state",
  "version": 1,
  "props": {
    "icon": "sparkles",
    "title": "No comments yet",
    "message": "Once reviewers weigh in, their notes will show up here.",
    "cta": "Invite a reviewer",
    "tone": "violet"
  }
}
```

### `divider-label`

```ui-block
{
  "type": "divider-label",
  "version": 1,
  "props": {
    "label": "Earlier this week"
  }
}
```

### `custom-list`

```ui-block
{
  "type": "custom-list",
  "version": 1,
  "props": {
    "title": "Revision order",
    "ordered": true,
    "tone": "violet",
    "items": [
      {
        "label": "Chapter 9 \u2014 intro tightening",
        "meta": "in progress"
      },
      {
        "label": "Chapter 12 \u2014 instrumentation section",
        "meta": "queued"
      },
      {
        "label": "Chapter 13 \u2014 deadline confirm",
        "meta": "blocked",
        "tone": "amber"
      }
    ]
  }
}
```
