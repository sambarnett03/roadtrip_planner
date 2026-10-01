# Utility/html_edits.py
import os
import json

def insert_buttons(html_path, buttons):
    """
    Appends a stack of buttons to a Folium-generated HTML file.

    Parameters:
    - html_path (str): Path to the HTML file.
    - buttons (list of tuples): Each tuple is (label, href).
    """
    button_container = '''
    <div id="button-container">
    {buttons_html}
    </div>

    <style>
      #button-container {{
        position: absolute;
        bottom: 5vh;
        left: 3vw;
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 1vh;
        z-index: 9999;
      }}

      .action-button {{
        background-color: white;
        padding: 10px 15px;
        border-radius: 8px;
        font-weight: bold;
        color: #007BFF;
        text-decoration: none;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
        transition: background-color 0.2s ease;
      }}

      .action-button:hover {{
        background-color: #f0f0f0;
      }}
    </style>
    '''

    buttons_html = "\n".join(
        f'<a href="{href}" class="action-button">{label}</a>' for label, href in buttons
    )

    full_html = button_container.format(buttons_html=buttons_html)

    with open(html_path, 'r', encoding='utf-8') as file:
        content = file.read()

    # Avoid duplicating if already inserted
    if '<div id="button-container">' not in content:
        updated_content = content.replace('</body>', full_html + '\n</body>')
        with open(html_path, 'w', encoding='utf-8') as file:
            file.write(updated_content)


def insert_sidebar(html_path, map_id, owner_id, firebase_config=None):
    """
    Injects a sidebar for notes into the HTML.
    Configures Firestore to use users/{owner_id}/maps/{map_id}/planning/notes
    Includes Authentication listener to prevent permission errors on load.
    """
    
    # Default config if none provided
    if not firebase_config:
        firebase_config = {
            "apiKey": "AIzaSyCEqG8QpT_6mf03SjJtn83g8pVo5NAVrCU",
            "authDomain": "roadmap-planner-87b0a.firebaseapp.com",
            "projectId": "roadmap-planner-87b0a",
            "storageBucket": "roadmap-planner-87b0a.firebasestorage.app",
            "messagingSenderId": "194176720157",
            "appId": "1:194176720157:web:07e32a7b0b14470c94d5f4",
            "measurementId": "G-Z91BDQR23Y"
        }

    # Serialize config to JSON for injection
    config_json = json.dumps(firebase_config)

    sidebar_code = f"""
    <style>
      #mySidebar {{
          height: 100%;
          width: 0;
          position: fixed;
          z-index: 1000;
          top: 0;
          right: 0;
          left: auto;
          background-color: white;
          overflow-x: hidden;
          overflow-y: auto;
          transition: 0.3s;
          padding-top: 60px;
          box-shadow: -2px 0 5px rgba(0,0,0,0.5);
      }}

      #mySidebar [contenteditable] {{
        width: 80%;
        max-height: 45vh;
        margin: 20px;
        padding: 10px;
        overflow-y: auto;
        border: 1px solid #ccc;
        font-family: Arial, sans-serif;
        resize: none;
        display: block;
        line-height: 1.4;
        min-height: 150px;
      }}

      /* Visual cue for read-only/loading state */
      #mySidebar [contenteditable="false"] {{
        background-color: #f9f9f9;
        color: #888;
        cursor: not-allowed;
      }}

      #mySidebar .closebtn {{
        position: absolute;
        top: 0;
        left: 25px;
        font-size: 36px;
      }}

      #openBtn {{
        position: fixed;
        top: 20px;
        right: 20px;
        left: auto;
        z-index: 1001;
        background-color: white;
        padding: 10px;
        border: 1px solid gray;
        cursor: pointer;
        box-shadow: 1px 1px 5px rgba(0,0,0,0.3);
      }}

      .toggle-container {{
        margin: 0 20px 10px 20px;
        font-family: Arial, sans-serif;
      }}

      .pdf-section {{
        margin: 0 20px 30px 20px;
        font-family: Arial, sans-serif;
        font-size: 13px;
      }}

      .pdf-section h4 {{
        margin: 10px 0 6px 0;
        font-size: 14px;
      }}

      #pdfList {{
        list-style: none;
        padding: 0;
        margin: 0 0 10px 0;
      }}

      #pdfList li {{
        padding: 6px 0;
        border-bottom: 1px solid #eee;
      }}

      #pdfList .pdf-name {{
        font-weight: bold;
        color: #007BFF;
        text-decoration: none;
        word-break: break-word;
      }}

      #pdfList .pdf-meta {{
        color: #888;
        font-size: 11px;
        margin-top: 2px;
      }}

      #pdfList .pdf-meta a,
      #pdfList .pdf-meta button {{
        color: #007BFF;
        background: none;
        border: none;
        padding: 0;
        margin-left: 6px;
        font-size: 11px;
        cursor: pointer;
        text-decoration: underline;
      }}

      #pdfList .pdf-meta button {{
        color: #c0392b;
      }}

      #pdfList .pdf-empty {{
        color: #888;
        border-bottom: none;
      }}

      #pdfUploadForm input[type="text"] {{
        width: 100%;
        box-sizing: border-box;
        padding: 5px;
        margin-bottom: 6px;
      }}

      #pdfUploadForm input[type="file"] {{
        width: 100%;
        margin-bottom: 6px;
      }}

      #pdfStatus {{
        margin-top: 6px;
        color: #555;
      }}
    </style>

    <div id="mySidebar">
      <a href="javascript:void(0)" class="closebtn" onclick="closeSidebar()">×</a>
      <div class="toggle-container">
        <label>
          <input type="checkbox" id="toggleMode" />
          Shared mode (Live)
        </label>
      </div>
      <div id="sharedContent" contenteditable="false"></div>

      <div class="pdf-section">
        <h4 id="pdfHeading">Shared files</h4>
        <ul id="pdfList"></ul>
        <form id="pdfUploadForm">
          <input type="text" id="pdfDisplayName" maxlength="120" placeholder="Display name (optional)">
          <input type="file" id="pdfFile" accept="application/pdf,.pdf" required>
          <button type="submit" id="pdfUploadBtn">Upload PDF</button>
          <div id="pdfStatus"></div>
        </form>
      </div>
    </div>
    <div id="openBtn" onclick="openSidebar()">☰ Notes &amp; Files</div>

    <script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js"></script>
    <script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-auth-compat.js"></script>
    <script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore-compat.js"></script>

    <script>
      const sidebar = document.getElementById("mySidebar");
      const editableDiv = document.getElementById("sharedContent");
      const toggle = document.getElementById("toggleMode");

      function openSidebar() {{
        sidebar.style.width = "300px";
      }}

      function closeSidebar() {{
        sidebar.style.width = "0";
      }}

      // Initialize Firebase
      const firebaseConfig = {config_json};

      if (!firebase.apps.length) {{
          firebase.initializeApp(firebaseConfig);
      }}
      const db = firebase.firestore();
      const auth = firebase.auth();

      // IDs injected from Python
      const ownerId = "{owner_id}";
      const mapId = "{map_id}";
      
      // Reference to the shared note
      const docRef = db.collection("users").doc(ownerId)
                       .collection("maps").doc(mapId)
                       .collection("planning").doc("notes");

      let unsubscribe = null;
      let currentUser = null; 

      // --- AUTH LISTENER ---
      // This waits for the browser to verify the user session.
      // Without this, Firestore requests fail immediately on page load.
      auth.onAuthStateChanged((user) => {{
        if (user) {{
          console.log("Sidebar: User signed in:", user.uid);
          currentUser = user;
          
          // If we are already in shared mode, trigger load now that we have a user
          if (toggle.checked) {{
             loadShared(); 
          }}
        }} else {{
          console.log("Sidebar: User currently signed out.");
          currentUser = null;
          if (toggle.checked) {{
             editableDiv.innerHTML = "Please sign in to view shared notes.";
          }}
        }}
      }});

      function loadShared() {{
        // Lock editing while loading
        editableDiv.contentEditable = "false";
        
        // If auth isn't ready yet, show waiting message.
        // onAuthStateChanged will call this function again once ready.
        if (!currentUser) {{
            editableDiv.innerHTML = "Verifying access...";
            return;
        }}

        // 1. Clear old listener if exists
        if (unsubscribe) unsubscribe();

        // 2. Start listening to the document
        unsubscribe = docRef.onSnapshot((doc) => {{
          const dbText = (doc.exists && doc.data().text) ? doc.data().text : "";

          // Only update the HTML if the user isn't currently typing
          if (document.activeElement !== editableDiv) {{
            editableDiv.innerHTML = dbText;
          }}
          
          // 3. Unlock editing once data is received
          if (editableDiv.contentEditable === "false") {{
             editableDiv.contentEditable = "true";
             
             // Attach save handler now that it is safe
             editableDiv.oninput = () => {{
                docRef.set({{ text: editableDiv.innerHTML }}, {{ merge: true }})
                .catch((error) => {{
                    console.error("Error saving note:", error);
                }});
             }};
          }}
        }}, (error) => {{
            console.error("Error loading shared notes:", error);
            if (error.code === 'permission-denied') {{
                editableDiv.innerHTML = "Access Denied: You are not listed as a collaborator.";
            }} else {{
                editableDiv.innerHTML = "Error loading notes: " + error.message;
            }}
        }});
      }}

      function loadPersonal() {{
        // Stop listening to Firestore updates
        if (unsubscribe) unsubscribe(); 

        const saved = localStorage.getItem("personalText_" + mapId);
        editableDiv.innerHTML = saved || "";
        
        editableDiv.contentEditable = "true";
        
        editableDiv.oninput = () => {{
          localStorage.setItem("personalText_" + mapId, editableDiv.innerHTML);
        }};
      }}

      // --- PDF ATTACHMENTS ---
      // Shared mode lists PDFs everyone on the map can see; personal mode
      // lists PDFs only the current user can see. Served by the Flask /api/pdfs routes.
      const pdfHeading = document.getElementById("pdfHeading");
      const pdfList = document.getElementById("pdfList");
      const pdfUploadForm = document.getElementById("pdfUploadForm");
      const pdfDisplayName = document.getElementById("pdfDisplayName");
      const pdfFile = document.getElementById("pdfFile");
      const pdfUploadBtn = document.getElementById("pdfUploadBtn");
      const pdfStatus = document.getElementById("pdfStatus");
      const PDF_MAX_BYTES = 10 * 1024 * 1024;
      let sharedUploadError = null;

      function pdfVisibility() {{
        return toggle.checked ? "shared" : "private";
      }}

      function pdfQuery(extra) {{
        const params = new URLSearchParams({{ map_id: mapId, owner_id: ownerId }});
        for (const key in (extra || {{}})) params.set(key, extra[key]);
        return params.toString();
      }}

      function formatSize(bytes) {{
        if (bytes < 1024 * 1024) return Math.max(1, Math.round(bytes / 1024)) + " KB";
        return (bytes / (1024 * 1024)).toFixed(1) + " MB";
      }}

      function pdfMessage(text) {{
        pdfList.innerHTML = "";
        const li = document.createElement("li");
        li.className = "pdf-empty";
        li.textContent = text;
        pdfList.appendChild(li);
      }}

      function renderPdfs(pdfs) {{
        if (!pdfs.length) {{
          pdfMessage(pdfVisibility() === "shared" ? "No shared files yet." : "No private files yet.");
          return;
        }}
        pdfList.innerHTML = "";
        for (const pdf of pdfs) {{
          const li = document.createElement("li");

          const view = document.createElement("a");
          view.className = "pdf-name";
          view.href = "/api/pdfs/" + encodeURIComponent(pdf.id) + "?" + pdfQuery();
          view.target = "_blank";
          view.rel = "noopener";
          view.textContent = pdf.display_name;
          view.title = pdf.filename;
          li.appendChild(view);

          const meta = document.createElement("div");
          meta.className = "pdf-meta";
          meta.appendChild(document.createTextNode(formatSize(pdf.size)));

          const download = document.createElement("a");
          download.href = "/api/pdfs/" + encodeURIComponent(pdf.id) + "?" + pdfQuery({{ download: "1" }});
          download.textContent = "Download";
          meta.appendChild(download);

          if (pdf.can_delete) {{
            const del = document.createElement("button");
            del.type = "button";
            del.textContent = "Delete";
            del.onclick = () => deletePdf(pdf);
            meta.appendChild(del);
          }}

          li.appendChild(meta);
          pdfList.appendChild(li);
        }}
      }}

      async function loadPdfs() {{
        const visibility = pdfVisibility();
        pdfHeading.textContent = visibility === "shared" ? "Shared files" : "My private files";
        pdfMessage("Loading…");
        try {{
          const resp = await fetch("/api/pdfs?" + pdfQuery({{ visibility: visibility }}));
          const data = await resp.json();
          if (!resp.ok) throw new Error(data.error || resp.statusText);
          if (visibility !== pdfVisibility()) return; // mode toggled while loading
          // Viewers can read shared files but not add them; remember why so the
          // upload form can explain it instead of failing silently.
          sharedUploadError = data.can_upload_shared ? null : data.upload_shared_error;
          renderPdfs(data.pdfs || []);
        }} catch (err) {{
          pdfMessage("Could not load files: " + err.message);
        }}
      }}

      async function deletePdf(pdf) {{
        if (!confirm('Delete "' + pdf.display_name + '"?')) return;
        try {{
          const resp = await fetch("/api/pdfs/delete", {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify({{ map_id: mapId, owner_id: ownerId, pdf_id: pdf.id }})
          }});
          const data = await resp.json();
          if (!resp.ok) throw new Error(data.error || resp.statusText);
          loadPdfs();
        }} catch (err) {{
          alert("Could not delete file: " + err.message);
        }}
      }}

      pdfFile.onchange = () => {{
        const file = pdfFile.files[0];
        pdfDisplayName.placeholder = file ? file.name.replace(/\\.pdf$/i, "") : "Display name (optional)";
      }};

      pdfUploadForm.onsubmit = async (e) => {{
        e.preventDefault();
        const file = pdfFile.files[0];
        if (!file) return;
        if (pdfVisibility() === "shared" && sharedUploadError) {{
          pdfStatus.textContent = sharedUploadError;
          return;
        }}
        if (file.size > PDF_MAX_BYTES) {{
          pdfStatus.textContent = "That PDF is too large (max 10 MB).";
          return;
        }}

        const form = new FormData();
        form.append("file", file);
        form.append("display_name", pdfDisplayName.value.trim());
        form.append("visibility", pdfVisibility());
        form.append("map_id", mapId);
        form.append("owner_id", ownerId);

        pdfUploadBtn.disabled = true;
        pdfStatus.textContent = "Uploading…";
        try {{
          const resp = await fetch("/api/pdfs/upload", {{ method: "POST", body: form }});
          const data = await resp.json();
          if (!resp.ok) throw new Error(data.error || resp.statusText);
          pdfUploadForm.reset();
          pdfDisplayName.placeholder = "Display name (optional)";
          pdfStatus.textContent = "";
          loadPdfs();
        }} catch (err) {{
          pdfStatus.textContent = "Upload failed: " + err.message;
        }} finally {{
          pdfUploadBtn.disabled = false;
        }}
      }};

      // Set initial mode on page load
      window.onload = () => {{
        const mode = localStorage.getItem("noteMode") || "shared";
        toggle.checked = mode === "shared";

        if (mode === "shared") {{
          loadShared();
        }} else {{
          loadPersonal();
        }}
        loadPdfs();
      }};

      // Handle Toggle Switch
      toggle.onchange = () => {{
        const newMode = toggle.checked ? "shared" : "personal";
        localStorage.setItem("noteMode", newMode);

        if (newMode === "shared") {{
          loadShared();
        }} else {{
          loadPersonal();
        }}
        pdfStatus.textContent = "";
        loadPdfs();
      }};
    </script>
    """

    # Inject sidebar code into HTML file
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
        # Ensure mobile responsiveness
        if "<meta name=\"viewport\"" not in html:
            html = html.replace("<head>", "<head>\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">")

    # Only inject if not already present
    if "id=\"mySidebar\"" not in html:
        html = html.replace("</body>", sidebar_code + "\n</body>")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)