```mermaid
erDiagram
    guild_members {
        bigint user_id
        text username
        text nickname
        timestamp first_joined_at
        timestamp last_joined_at
        timestamp left_at
    }
```
