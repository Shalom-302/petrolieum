# Plugin Dependencies Management

This document explains how to manage dependencies for plugins in Kaapi.

## Dependency Structure

Kaapi uses a modular architecture for dependency management :

1. **requirements.txt principal** : Contains base dependencies required for the core of Kaapi.
2. **Fichiers requirements.txt spécifiques à chaque plugin** : Each plugin has its own `requirements.txt` file in its directory.

## How It Works

### For Plugin Developers

If you are developing a plugin :

1. Create a `requirements.txt` file in the plugin directory.
2. Add only the dependencies specific to your plugin.
3. Specify the minimum recommended versions.
4. Add comments to explain why each dependency is necessary.

Example :

```txt
# Plugin Advanced Internationalization
pycountry>=22.3.5  # For managing country names and codes
babel>=2.12.1      # For supporting localized date/time formats
polib>=1.2.0       # For importing/exporting PO/POT files
```

### For Users

To install all dependencies :

1. **Installation of base dependencies** :

   ```bash
   pip install -r requirements.txt
   ```

2. **Installation of plugin dependencies** :

   ```bash
   python install_plugin_requirements.py
   ```

3. **Installation of a specific plugin's dependencies** :

   ```bash
   python install_plugin_requirements.py --plugin advanced_i18n
   ```

4. **Generate a consolidated requirements file** :

   ```bash
   python install_plugin_requirements.py --generate
   ```

   This will create a `requirements-plugins.txt` file with all plugin dependencies.

## Resolution of Conflicts

If two plugins require different versions of the same dependency :

1. The script `install_plugin_requirements.py` installs the latest version.
2. To manually resolve a conflict, specify the exact version in the `requirements.txt` file.

## Good Practices

1. **Minimize dependencies** : Only include dependencies absolutely necessary.
2. **Specify versions** : Use `>=` to indicate the minimum required version.
3. **Document** : Add comments to explain the usage of each dependency.
4. **Share common dependencies** : If multiple plugins use the same library, consider moving it to the `requirements.txt` principal.

## Compatibility Tests

Before each release, run :

```bash
python install_plugin_requirements.py --generate
pip install -r requirements.txt -r requirements-plugins.txt
pytest
```

This ensures that all dependencies are compatible and work together.
