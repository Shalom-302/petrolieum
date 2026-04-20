
### A Plugins Directory Structure
Plugins empower Kaapi to be extended or customized in a low-friction way.
A folder backend/app/plugins designed for any custom “plugins.” Each plugin can have:

A lifecycle (e.g., on_startup, on_shutdown).
Optional database schema additions (extra tables).
Optional routes mounted onto the main FastAPI app.
This allows users of Kaapi to drop in a folder with code to add new behaviors.

```bash
app/
  └── plugins/
      ├── __init__.py
      ├── advanced_logging/
      │   ├── models.py
      │   ├── routes.py
      │   └── main.py
      └── custom_auth/
          ├── models.py
          ├── routes.py
          └── main.py

```

### Auto-Discover and Mount Plugin Routes
On startup, do a directory scan (like with your dynamic models) to find plugins/*/main.py files. For each plugin:

- Import it automatically.
- Check if it has a function or attribute that returns a FastAPI router.
- Mount that router at a plugin-specific prefix, like /plugins/advanced_logging.


### List of interesting plugins

1\. Create a New Folder for the Plugin
--------------------------------------

1.  mkdir app/plugins/my\_new\_plugin
    
2.  **Create** a main.py (and optionally a schemas.py, tasks.py, etc.).
    
    *   The critical piece is that **main.py** has a function get\_router() which returns a FastAPI APIRouter.
        

### Minimal Example: app/plugins/my\_new\_plugin/main.py

````python
from fastapi import APIRouter  
  def get_router():      
    router = APIRouter()      
    @router.get("/hello")      
    def say_hello():          
      return {"message": "Hello from my_new_plugin"}      
    return router
````

**Key point**: The scanning system looks for get\_router() inside main.py.