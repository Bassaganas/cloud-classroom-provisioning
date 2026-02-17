# Documentation Website

This directory contains the Docusaurus documentation site for Cloud Classroom Provisioning.

## Development

```bash
cd website
npm install
npm start
```

This starts a local development server and opens up a browser window. Most changes are reflected live without having to restart the server.

## Build

```bash
cd website
npm run build
```

This command generates static content into the `build` directory and can be served using any static contents hosting service.

## Deployment

The documentation is automatically deployed to GitHub Pages via GitHub Actions when changes are pushed to the `main` branch.

To manually deploy:

```bash
cd website
npm run build
# Then push the build directory to the gh-pages branch
```

## Structure

- `docs/` - Documentation markdown files
- `src/` - React components and pages
- `static/` - Static assets (images, etc.)
- `docusaurus.config.ts` - Docusaurus configuration
- `sidebars.ts` - Sidebar navigation configuration
