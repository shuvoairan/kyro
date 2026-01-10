```mermaid
erDiagram
    users {
        bigint id PK
        text username
        text nickname
        text discord_id
        int first_joined_at
        int last_joined_at
        int left_at
    }
```
