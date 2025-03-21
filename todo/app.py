"""This builds the app.py that we will run the app with"""

# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/01_app.ipynb.

# %% auto 0
__all__ = ['conn', 'cursor', 'sample_users', 'sample_todos', 'beforeware', 'exception_handlers', 'hdrs', 'app', 'rt',
           'AccessLevel', 'get_required_access_level', 'get_user_access_level', 'get_user_by_credentials',
           'get_all_users', 'update_user', 'get_todos_by_user', 'get_all_todos', 'add_todo', 'update_todo_status',
           'delete_todo', 'is_htmx_request', 'Layout', 'respond', 'create_todo_item', 'TextField', 'auth_beforeware']

# %% ../nbs/01_app.ipynb 2
import json
from enum import IntEnum
from fasthtml.common import *
from fasthtml.jupyter import *
import apsw


# %% ../nbs/01_app.ipynb 3
class AccessLevel(IntEnum):
    PUBLIC = 0
    NOT_AUTHENTICATED = 1
    FREE_USER = 2
    PREMIUM_USER = 3
    ADMIN = 4

# %% ../nbs/01_app.ipynb 5
# Set up the SQLite database
# Create in-memory database
conn = apsw.Connection(":memory:")
cursor = conn.cursor()

# Create users table
cursor.execute("""
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    level INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Create todos table
cursor.execute("""
CREATE TABLE todos (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    completed BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
)
""")

# %% ../nbs/01_app.ipynb 6
# Insert some sample users
sample_users = [
    (1, "admin", "admin123", AccessLevel.ADMIN, "2023-01-01"),
    (2, "premium", "password", AccessLevel.PREMIUM_USER, "2023-01-02"),
    (3, "free", "password", AccessLevel.FREE_USER, "2023-01-03"),
    (4, "guest", "password", AccessLevel.NOT_AUTHENTICATED, "2023-01-04")
]

cursor.executemany(
    "INSERT INTO users VALUES (?, ?, ?, ?, ?)",
    sample_users
)

# %% ../nbs/01_app.ipynb 7
# Insert some sample todos
sample_todos = [
    (1, 1, "Admin task 1", "Description for admin task 1", 0, "2023-01-01"),
    (2, 1, "Admin task 2", "Description for admin task 2", 1, "2023-01-02"),
    (3, 2, "Premium user task", "Description for premium user task", 0, "2023-01-03"),
    (4, 3, "Free user task", "Description for free user task", 1, "2023-01-04")
]

cursor.executemany(
    "INSERT INTO todos VALUES (?, ?, ?, ?, ?, ?)",
    sample_todos
)

# %% ../nbs/01_app.ipynb 10
# Helper functions for authentication and database access
def get_required_access_level(path):
    """Map routes to required access levels"""
    if path == '/' or path.startswith('/public'):
        return AccessLevel.PUBLIC
    elif path.startswith('/account') or path.startswith('/login'):
        return AccessLevel.NOT_AUTHENTICATED
    elif path.startswith('/dashboard'):
        return AccessLevel.FREE_USER
    elif path.startswith('/todos/all'):
        return AccessLevel.ADMIN
    elif path.startswith('/profile'):
        return AccessLevel.PREMIUM_USER
    elif path.startswith('/admin'):
        return AccessLevel.ADMIN
    else:
        # Default protection level
        return AccessLevel.FREE_USER

def get_user_access_level(auth):
    """Get user's access level from auth data"""
    if not auth:
        return AccessLevel.PUBLIC
    return auth.get('level', AccessLevel.PUBLIC)

def get_user_by_credentials(username, password):
    """Get user from database by username and password"""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, level FROM users WHERE username = ? AND password = ?",
        (username, password)
    )
    row = cursor.fetchone()
    
    if not row:
        return None
    
    return {
        'id': row[0],
        'username': row[1],
        'level': row[2]
    }

def get_all_users():
    """Get all users from database"""
    cursor = conn.cursor()
    users = []
    for row in cursor.execute("SELECT id, username, level FROM users"):
        users.append({
            'id': row[0],
            'username': row[1],
            'level': row[2]
        })
    return users

def update_user(user_id, level):
    """Update user level"""
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET level = ? WHERE id = ?",
        (level, user_id)
    )
    return cursor.getconnection().changes() > 0

# New todo management functions
def get_todos_by_user(user_id):
    """Get all todos for a specific user"""
    cursor = conn.cursor()
    todos = []
    for row in cursor.execute("""
        SELECT id, title, description, completed, created_at 
        FROM todos 
        WHERE user_id = ?
        ORDER BY created_at DESC
        """, (user_id,)):
        todos.append({
            'id': row[0],
            'title': row[1],
            'description': row[2],
            'completed': bool(row[3]),
            'created_at': row[4]
        })
    return todos

def get_all_todos():
    """Get all todos (for admin)"""
    cursor = conn.cursor()
    todos = []
    for row in cursor.execute("""
        SELECT t.id, t.user_id, u.username, t.title, t.description, t.completed, t.created_at 
        FROM todos t
        JOIN users u ON t.user_id = u.id
        ORDER BY t.created_at DESC
        """):
        todos.append({
            'id': row[0],
            'user_id': row[1],
            'username': row[2],
            'title': row[3],
            'description': row[4],
            'completed': bool(row[5]),
            'created_at': row[6]
        })
    return todos

def add_todo(user_id, title, description=""):
    """Add a new todo for a user"""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO todos (user_id, title, description) VALUES (?, ?, ?)",
        (user_id, title, description)
    )
    return cursor.getconnection().last_insert_rowid()

def update_todo_status(todo_id, completed):
    """Update the completed status of a todo"""
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE todos SET completed = ? WHERE id = ?",
        (1 if completed else 0, todo_id)
    )
    return cursor.getconnection().changes() > 0

def delete_todo(todo_id):
    """Delete a todo"""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
    return cursor.getconnection().changes() > 0


# %% ../nbs/01_app.ipynb 12
def is_htmx_request(req):
    """Helper function to determine if request is from HTMX"""
    return "HX-Request" in req.headers

def Layout(header=None, nav=None, main=None, auth=None, **kwargs):
    "Dashboard layout with responsive drawer navigation"
    drawer_toggle = Button(
        "☰",  # Simple menu icon as text
        cls="drawer-toggle icon-button md-n-below-flex",
        aria_label="Toggle navigation menu",
        onclick="htmx.toggleClass(htmx.find('nav'), 'drawer-open'); htmx.toggleClass(htmx.find('.overlay'), 'drawer-open')"
    )
    
    layout_css = """
    me { 
      display: grid;
      height: calc(100svh - var(--size-2));
      grid-template:
        "header header" auto
        "nav    main" 1fr
        / auto   1fr;
      gap: var(--size-1);
      margin: var(--size-1);
      margin-bottom: 0;
    }
    
    me > header {grid-area: header; display: flex;}
    me > nav  {grid-area:nav;  overflow-y:auto;}
    me > main {grid-area:main; overflow-y:auto;}
    me .drawer-toggle {display:none;}
    .overlay {display:none; position:fixed; top:0; left:0; width:100vw; height:100vh; background:rgb(0 0 0 / 0.3); z-index:var(--layer-4);}
    
    @media (max-width: 768px) {
      me {
        grid-template:
          " header header" auto
          " main   main  " 1fr
          / 1fr    1fr;
      }
      
      me .drawer-toggle {display: block;}
      me > nav {position:fixed; top:0; left:0; width:100vw; height:100svh; width: 80%; max-width: 300px; z-index: var(--layer-5); transform: translateX(-100%); transition: transform 0.3s ease;}
      me > nav.drawer-open {transform:translateX(0);}
      .overlay.drawer-open {display: block;}
    }
    """
    
    # Default navigation based on auth level
    if nav is None:
        nav_items = [
            Li(A("Home", href="/", hx_get="/", hx_target="#main", hx_push_url="true")),
        ]
        
        if auth:
            # Add authenticated user navigation
            nav_items.extend([
                Li(A("My Todos", href="/dashboard", hx_get="/dashboard", hx_target="#main", hx_push_url="true")),
                Li(A("Profile", href="/profile", hx_get="/profile", hx_target="#main", hx_push_url="true")),
            ])
            
            # Add admin-only navigation
            if auth.get('level') >= AccessLevel.ADMIN:
                nav_items.append(
                    Li(A("All Todos", href="/todos/all", hx_get="/todos/all", hx_target="#main", hx_push_url="true"))
                )
                
            nav_items.append(Li(A("Logout", href="/logout")))
        else:
            # Add non-authenticated navigation
            nav_items.append(Li(A("Login", href="/login", hx_get="/login", hx_target="#main", hx_push_url="true")))
        
        nav = Ul(cls="nav-list")(*nav_items)
    
    # Default header
    if header is None:
        app_title = "Todo App"
        if auth:
            header = Div(cls="flex space-between align-center")(
                H1(app_title),
                Span(f"Welcome, {auth.get('username')}!")
            )
        else:
            header = H1(app_title)
    
    header_content = Div(cls="flex")(drawer_toggle, header) if header else drawer_toggle
    
    return Div(
        Style(layout_css),
        Div(cls="overlay", onclick="htmx.toggleClass(htmx.find('nav'), 'drawer-open'); htmx.toggleClass(htmx.find('.overlay'), 'drawer-open')"),
        Header(id="header")(header_content),
        Nav(id="nav", cls="card outlined")(nav) if nav else Nav(id="nav", cls="card outlined"),
        Main(id="main", cls="card tonal padding")(main) if main else Main(id="main", cls="card tonal padding"),
        **kwargs
    )

def respond(req, content, title="Todo App"):
    """Smart response factory with proper headers implementation"""
    auth = req.scope.get('auth')
    
    if is_htmx_request(req):
        # For HTMX requests, return just the content with proper headers
        return FtResponse(
            content, 
            headers={
                "Vary": "HX-Request, HX-Trigger"
            }
        )
    
    # For full page requests, use the Layout
    return Title(title), Layout(main=content, auth=auth)

def create_todo_item(todo, user_level=AccessLevel.FREE_USER):
    """Create a todo item component with appropriate actions"""
    actions = Div(cls="todo-actions")
    
    # Toggle completion status
    toggle_button = Button(
        "✓" if todo['completed'] else "□",
        cls="toggle-todo",
        hx_post=f"/todos/{todo['id']}/toggle",
        hx_target="closest .todo-item",
        hx_swap="outerHTML"
    )
    
    # Delete button
    delete_button = Button(
        "🗑️",
        cls="delete-todo",
        hx_delete=f"/todos/{todo['id']}",
        hx_target="closest .todo-item",
        hx_swap="outerHTML",
        hx_confirm="Are you sure you want to delete this todo?"
    )
    
    actions(toggle_button, delete_button)
    
    # Add username for admin view
    title_content = todo['title']
    if user_level >= AccessLevel.ADMIN and 'username' in todo:
        title_content = f"{title_content} (by {todo['username']})"
    
    return Div(
        cls=f"todo-item {'completed' if todo['completed'] else ''}",
        id=f"todo-{todo['id']}"
    )(
        H3(title_content),
        P(todo['description']) if todo['description'] else None,
        P(f"Created: {todo['created_at']}", cls="todo-date"),
        actions
    )


# %% ../nbs/01_app.ipynb 14
def TextField(label_text, input_name, **kwargs):
    """Text field component using OpenPropsUI styling"""
    # Extract kwargs with defaults
    placeholder = kwargs.get('placeholder', '')
    required = kwargs.get('required', False)
    supporting_text = kwargs.get('supporting_text', '')
    input_type = kwargs.get('type', 'text')
    error = kwargs.get('error', False)
    auto_fit = kwargs.get('auto_fit', False)
    
    # Build the field class
    field_classes = []
    
    # Add variants
    if kwargs.get('filled', False):
        field_classes.append('filled')
    
    # Add size
    if kwargs.get('small', False):
        field_classes.append('small')
    
    # Add validation
    if error:
        field_classes.append('error')
    
    # Add auto-fit
    if auto_fit:
        field_classes.append('auto-fit')
    
    # Add any custom classes
    if 'cls' in kwargs:
        field_classes.append(kwargs['cls'])
    
    field_class = ' '.join(field_classes)
    
    # Build the components
    label_components = [
        Span(label_text, cls="label"),
        Input(
            type=input_type, 
            name=input_name, 
            placeholder=placeholder,
            required=required
        )
    ]
    
    # Add supporting text if provided
    if supporting_text:
        label_components.append(Span(supporting_text, cls="supporting-text"))
    
    return Label(
        *label_components,
        cls=f"field {field_class}".strip()
    )

# %% ../nbs/01_app.ipynb 17
def auth_beforeware(req, sess):
    """Beforeware function to handle authentication and authorization"""
    # Set default authentication state
    auth = sess.get('auth', None)
    req.scope['auth'] = auth
    
    # Extract the required access level from the route
    path = str(req.url.path)
    required_level = get_required_access_level(path)
    
    # Get the user's current access level
    user_level = get_user_access_level(auth)
    
    # For debugging
    print(f"Path: {path}, Required level: {required_level}, User level: {user_level}")
    
    # Enforce authentication if needed
    if required_level >= AccessLevel.NOT_AUTHENTICATED and not auth:
        return RedirectResponse('/login', status_code=303)
        
    # Check if user has sufficient access
    if user_level < required_level:
        return RedirectResponse('/access-denied', status_code=303)


# %% ../nbs/01_app.ipynb 18
beforeware = Beforeware(
    auth_beforeware,
    skip=[r'/favicon\.ico', r'/static/.*', r'.*\.css', r'.*\.js', '/login', '/access-denied']
)

exception_handlers={
    404: lambda req, exc: Titled("404: I don't exist!", A(href="/")("home")),
    418: lambda req, exc: Titled("418: I'm Lost..😞",  A(href="/")("home"))
}

hdrs = (
    Link(rel='stylesheet', href='static/css/main.css'),
)


app, rt = fast_app(
    pico=False,
    hdrs=hdrs,
    exception_handlers=exception_handlers,
    before=beforeware,
    debug=True
)

