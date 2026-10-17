"""Seed HR data for the mock backend.

Fictional data for local development and demos only. Swap for Azure SQL /
Azure AI Search in AzureBackend (see server.py) once credentials exist.
"""

from __future__ import annotations

from typing import Any


EMPLOYEES: list[dict[str, Any]] = [
    {
        "id": "E1001",
        "name": "Sarah Chen",
        "title": "Senior Product Manager",
        "department": "Product",
        "email": "sarah.chen@example.com",
        "manager": "Priya Nair",
        "location": "Seattle, WA",
        "start_date": "2021-03-15",
        "employment_type": "Full-time",
        "salary": 165000,
        "currency": "USD",
        "pay_frequency": "annual",
        "pto": {
            "accrual_days_per_year": 20,
            "used_days": 8,
            "remaining_days": 12,
            "as_of": "2026-08-01",
        },
        "benefits": {
            "medical": "PPO Plus (employee + spouse)",
            "dental": "Delta Dental Standard",
            "vision": "VSP Basic",
            "retirement_401k_percent": 6,
            "employer_match_percent": 4,
        },
    },
    {
        "id": "E1002",
        "name": "Marcus Johnson",
        "title": "Software Engineer II",
        "department": "Engineering",
        "email": "marcus.johnson@example.com",
        "manager": "Priya Nair",
        "location": "Austin, TX",
        "start_date": "2022-09-01",
        "employment_type": "Full-time",
        "salary": 142000,
        "currency": "USD",
        "pay_frequency": "annual",
        "pto": {
            "accrual_days_per_year": 18,
            "used_days": 15,
            "remaining_days": 3,
            "as_of": "2026-08-01",
        },
        "benefits": {
            "medical": "HDHP + HSA (employee only)",
            "dental": "Delta Dental Standard",
            "vision": "None",
            "retirement_401k_percent": 10,
            "employer_match_percent": 4,
        },
    },
    {
        "id": "E1003",
        "name": "Priya Nair",
        "title": "Director of Product & Engineering",
        "department": "Product",
        "email": "priya.nair@example.com",
        "manager": "Dana Whitfield",
        "location": "Seattle, WA",
        "start_date": "2019-01-07",
        "employment_type": "Full-time",
        "salary": 210000,
        "currency": "USD",
        "pay_frequency": "annual",
        "pto": {
            "accrual_days_per_year": 25,
            "used_days": 10,
            "remaining_days": 15,
            "as_of": "2026-08-01",
        },
        "benefits": {
            "medical": "PPO Plus (family)",
            "dental": "Delta Dental Premium",
            "vision": "VSP Plus",
            "retirement_401k_percent": 8,
            "employer_match_percent": 4,
        },
    },
    {
        "id": "E1004",
        "name": "Elena Rodriguez",
        "title": "UX Designer",
        "department": "Product",
        "email": "elena.rodriguez@example.com",
        "manager": "Sarah Chen",
        "location": "Remote (CA)",
        "start_date": "2023-06-12",
        "employment_type": "Full-time",
        "salary": 128000,
        "currency": "USD",
        "pay_frequency": "annual",
        "pto": {
            "accrual_days_per_year": 18,
            "used_days": 4,
            "remaining_days": 14,
            "as_of": "2026-08-01",
        },
        "benefits": {
            "medical": "PPO Standard (employee only)",
            "dental": "Delta Dental Standard",
            "vision": "VSP Basic",
            "retirement_401k_percent": 5,
            "employer_match_percent": 4,
        },
    },
    {
        "id": "E1005",
        "name": "Dana Whitfield",
        "title": "VP of Engineering",
        "department": "Engineering",
        "email": "dana.whitfield@example.com",
        "manager": "",
        "location": "Seattle, WA",
        "start_date": "2017-11-20",
        "employment_type": "Full-time",
        "salary": 275000,
        "currency": "USD",
        "pay_frequency": "annual",
        "pto": {
            "accrual_days_per_year": 28,
            "used_days": 6,
            "remaining_days": 22,
            "as_of": "2026-08-01",
        },
        "benefits": {
            "medical": "PPO Plus (family)",
            "dental": "Delta Dental Premium",
            "vision": "VSP Plus",
            "retirement_401k_percent": 12,
            "employer_match_percent": 4,
        },
    },
]


POLICIES: list[dict[str, Any]] = [
    {
        "title": "Paid Time Off (PTO) Policy",
        "section": "Accrual",
        "content": (
            "Full-time employees accrue PTO based on tenure: 18 days per year for "
            "the first 2 years, 20 days from years 3-5, and 25 days after 5 years. "
            "PTO accrues monthly and unused days roll over up to a cap of 10 days "
            "per year."
        ),
        "source": "HR-Handbook-2026.pdf, p.14",
    },
    {
        "title": "Paid Time Off (PTO) Policy",
        "section": "Requesting Leave",
        "content": (
            "PTO requests should be submitted at least 2 weeks in advance for "
            "planned absences and are approved by the employee's direct manager. "
            "Sick leave does not require advance notice."
        ),
        "source": "HR-Handbook-2026.pdf, p.15",
    },
    {
        "title": "Parental Leave Policy",
        "section": "Eligibility & Duration",
        "content": (
            "Employees who have been with the company for at least 12 months are "
            "eligible for 12 weeks of paid parental leave following the birth or "
            "adoption of a child. Leave must be taken within 12 months of the event."
        ),
        "source": "HR-Handbook-2026.pdf, p.22",
    },
    {
        "title": "Remote Work Policy",
        "section": "Eligibility",
        "content": (
            "Remote and hybrid arrangements are available to roles designated as "
            "remote-eligible. Fully remote employees must be available during core "
            "hours of 9am-3pm in their team's primary time zone."
        ),
        "source": "HR-Handbook-2026.pdf, p.31",
    },
    {
        "title": "401(k) Retirement Plan",
        "section": "Employer Match",
        "content": (
            "The company matches 100% of employee 401(k) contributions up to 4% of "
            "eligible compensation. Employees are immediately vested in employer "
            "matching contributions."
        ),
        "source": "Benefits-Guide-2026.pdf, p.8",
    },
]
