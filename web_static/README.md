# Web Static Assets

Place compiled/minified frontend assets (JS, CSS, images) here for the Flask
app to serve via the `static_folder` configuration in `src/web/server.py`.

Examples:
- `js/` for bundled scripts (e.g., scheduler UI helpers)
- `css/` for stylesheets
- `img/` for logos or icons

Note: The folder is intentionally empty to allow custom deployments. Static
files are resolved relative to this directory when referenced in templates.
