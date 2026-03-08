# Chat Tests

This directory contains tests for chat functionality.

## Test List

### TC_CHAT_001 - Chat History Isolation Between Users
- **Description**: Verify that User1's chat history, sessions, and messages are completely isolated from User2's chat history. Each user should only see their own messages, sessions, and have their own credits and pipelines.
- **Priority**: High
- **Tags**: chat, isolation, history, user1, user2, credits, sessions

### TC_CHAT_002 - User2 Creates and Sends Chat Message
- **Description**: Verify User2 can create a chat session and send messages
- **Priority**: High
- **Tags**: chat, message, user2

## Common Patterns

### Chat Message Flow
All chat tests follow this pattern:

1. Login as user
2. Wait for chat interface to load
3. Type a message
4. Send the message
5. Verify message appears in chat history
6. Verify message is correctly attributed

### Using ChatPanel Page Object

```python
from page_objects import ChatPanel

chat_panel = ChatPanel(page)
await chat_panel.wait_for_chat_ready()
await chat_panel.send_message("Hello, world!")
await chat_panel.verify_message_in_history("Hello, world!")
```

## Known Issues

None at this time.
