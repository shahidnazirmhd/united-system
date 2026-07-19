# Enterprise HR Platform

Backend
- Django 5
- Django REST Framework
- PostgreSQL
- Redis
- Celery

Frontend
- React
- TypeScript
- Tailwind
- shadcn/ui

Architecture
- Clean Architecture
- DDD
- SOLID
- Repository Pattern

Telegram

Telegram is NOT HR.

Telegram is only a client.

Modules

Employee
Leave
Attendance
Payroll
Performance
Recruitment
Approval
Notification

Every module must be independent.

No business logic inside Views.

All business logic inside Services.

Every module must expose REST APIs.

Frontend consumes APIs only.

Telegram consumes APIs only.