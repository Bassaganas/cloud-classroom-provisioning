# Commit Message Guidelines

## Format
Follow the Semantic Commit Message format strictly:

```
<type>(<scope>): <subject>
```

## Rules

- **Type** (required): Must be one of: `chore`, `docs`, `feat`, `fix`, `refactor`, `style`, `test`
- **Scope** (optional): Recommended for clarity
- **Subject** (required): Concise, reflects business logic
- **Output**: Single-line only, no summaries or bullet points

## When Writing Commits

1. Analyze the diff and determine the appropriate type
2. Add a scope if applicable
3. Write a concise subject line
4. Ensure the message matches the exact format: `<type>(<scope>): <subject>`
5. If the format is incorrect, regenerate until it matches exactly
6. Output only the commit message—nothing else

## Example

```
feat(auth): add user login validation
fix(api): resolve null reference exception
docs(readme): update installation steps
```