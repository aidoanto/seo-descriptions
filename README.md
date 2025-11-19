# Template project

This is my UV project template.

## What is a GitHub template repository?

A **template repository** is a special type of GitHub repository that serves as a starting point for new projects. Think of it as a "project blueprint" that you can use to quickly create new repositories with the same structure, files, and initial setup.

### How template repos differ from normal repos

**Template repository:**

- Has a "Use this template" button on GitHub
- When someone uses it, GitHub creates a **completely new repository** (not a fork)
- The new repo has no connection to the original template
- Perfect for project starters, boilerplates, and reusable project structures

**Normal repository:**

- Can be forked, but forks maintain a connection to the original
- Forked repos show "forked from" and can create pull requests back to the original
- Better for collaborative development and contributions

### Working with this template

#### If you want to use this template for a new project:

1. Click the **"Use this template"** button on GitHub
2. Choose a name for your new project
3. GitHub will create a brand new repository with all the files from this template
4. Clone your new repository and start coding!

#### If you want to update the template itself:

1. Make your changes directly in this repository
2. Commit and push your changes
3. The template is now updated for future users
4. **Note:** Existing projects created from this template won't automatically get your updates

#### If you want to convert this template to a regular project:

1. Go to your repository settings on GitHub
2. Scroll down to the "Template repository" section
3. Uncheck the "Template repository" option
4. This repository becomes a normal repo (no more "Use this template" button)

### Best practices for template repositories

- Keep template files generic and well-documented
- Use placeholder values that users can easily find and replace
- Include clear setup instructions (like this README!)
- Don't include sensitive information (use `.env.example` files instead)
- Test your template by creating a new project from it occasionally

### API keys

In .env you can find the following API keys should you need them.

They are all correct and tested.

```
OPENROUTER_API_KEY=""
REPLICATE_API_TOKEN=""
ASSEMBLYAI_API_KEY=""
```

The best LLMs to use through OpenRouter are currently:

* For simple tasks: `deepseek/deepseek-chat-v3-0324`
* For SOTA english language writing: `google/gemini-2.5-pro`
* For SOTA tool-calling performance and instruction following: `anthropic/claude-sonnet-4`
* Best cheap model able to use image inputs: `google/gemini-2.0-flash-001`

If you are using LLMs to retrieve data that will eventually be structured, you must use the Structured Outputs feature.

More on this in docs/api-docs.

## Cursor IDE Configuration

This template includes a `.vscode` folder with pre-configured settings for Cursor IDE. Since Cursor is based on VS Code, it uses the same configuration system.

### What's included:

- **`settings.json`**: Editor preferences, Python settings, file handling, and Cursor-specific configurations
- **`keybindings.json`**: Custom keyboard shortcuts for improved productivity
- **`extensions.json`**: Recommended extensions for Python development and general productivity

### How to use:

1. **Clone this template** to your new project
2. **Open the project in Cursor** - it will automatically detect the `.vscode` folder
3. **Install recommended extensions** - Cursor will prompt you to install the recommended extensions
4. **Customize as needed** - modify the configuration files to match your preferences

### Syncing across machines:

To use these same settings on multiple machines:

1. **Commit the `.vscode` folder** to your repository
2. **Clone the project** on other machines
3. **Open in Cursor** - settings will be automatically applied
4. **Install extensions** when prompted

### Customizing the configuration:

- **Settings**: Edit `.vscode/settings.json` to change editor behavior, themes, and tool preferences
- **Keybindings**: Modify `.vscode/keybindings.json` to add or change keyboard shortcuts
- **Extensions**: Update `.vscode/extensions.json` to add or remove recommended extensions

The configuration is designed for Python development with modern best practices, but you can easily adapt it for other languages or workflows.
