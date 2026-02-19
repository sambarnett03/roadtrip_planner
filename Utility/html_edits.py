
def insert_buttons(html_path, buttons):
    """
    Appends a stack of buttons to a Folium-generated HTML file.

    Parameters:
    - html_path (str): Path to the HTML file.
    - buttons (list of tuples): Each tuple is (label, href), e.g. [("Add Marker", "/form?location=France")]
    """
    button_container = '''
    <div id="button-container">
    {buttons_html}
    </div>

    <style>
      #button-container {{
        position: absolute;
        bottom: 5vh;
        right: 5vw;
        display: flex;
        flex-direction: column;
        align-items: flex-end;
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

    # Generate HTML for individual buttons
    buttons_html = "\n".join(
        f'<a href="{href}" class="action-button">{label}</a>' for label, href in buttons
    )

    # Final combined HTML block
    full_html = button_container.format(buttons_html=buttons_html)

    # Inject it just before </body>
    with open(html_path, 'r', encoding='utf-8') as file:
        content = file.read()

    updated_content = content.replace('</body>', full_html + '\n</body>')

    with open(html_path, 'w', encoding='utf-8') as file:
        file.write(updated_content)












def insert_sidebar(html_path):
    sidebar_code = """
    <!-- Sidebar CSS -->
    <style>
      #mySidebar {
        height: 100%;
        width: 0;
        position: fixed;
        z-index: 1000;
        top: 0;
        right: 0;
        left: auto;
        background-color: white;
        overflow-x: hidden;
        transition: 0.3s;
        padding-top: 60px;
        box-shadow: -2px 0 5px rgba(0,0,0,0.5);
      }

      #mySidebar [contenteditable] {
        width: 80%;
        max-height: 70vh;
        margin: 20px;
        padding: 10px;
        overflow-y: auto;
        border: 1px solid #ccc;
        font-family: Arial, sans-serif;
        resize: none;
        display: block;
        line-height: 1.4;
        min-height: 150px;
      }

      #mySidebar .closebtn {
        position: absolute;
        top: 0;
        left: 25px;
        font-size: 36px;
      }

      #openBtn {
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
      }

      .toggle-container {
        margin: 0 20px 10px 20px;
        font-family: Arial, sans-serif;
      }
    </style>

    <!-- Sidebar HTML -->
    <div id="mySidebar">
      <a href="javascript:void(0)" class="closebtn" onclick="closeSidebar()">×</a>
      <div class="toggle-container">
        <label>
          <input type="checkbox" id="toggleMode" />
          Shared mode
        </label>
      </div>
      <div id="sharedContent" contenteditable="true"></div>
    </div>
    <div id="openBtn" onclick="openSidebar()">☰ Info</div>

    <!-- Firebase SDKs -->
    <script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js"></script>
    <script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore-compat.js"></script>

    <!-- Sidebar JS with Toggle -->
    <script>
      const sidebar = document.getElementById("mySidebar");
      const editableDiv = document.getElementById("sharedContent");
      const toggle = document.getElementById("toggleMode");

      function openSidebar() {
        sidebar.style.width = "300px";
      }

      function closeSidebar() {
        sidebar.style.width = "0";
      }

      // Your Firebase config
        const firebaseConfig = {
        apiKey: "AIzaSyCEqG8QpT_6mf03SjJtn83g8pVo5NAVrCU",
        authDomain: "roadmap-planner-87b0a.firebaseapp.com",
        projectId: "roadmap-planner-87b0a",
        storageBucket: "roadmap-planner-87b0a.firebasestorage.app",
        messagingSenderId: "194176720157",
        appId: "1:194176720157:web:07e32a7b0b14470c94d5f4",
        measurementId: "G-Z91BDQR23Y"
        };

      firebase.initializeApp(firebaseConfig);
      const db = firebase.firestore();
      const docRef = db.collection("shared").doc("note");

      let unsubscribe = null;
      

      function loadShared() {
        docRef.get().then((doc) => {
          if (doc.exists) {
            editableDiv.innerHTML = doc.data().text || "";
          }
        });

        unsubscribe = docRef.onSnapshot((doc) => {
          if (doc.exists && document.activeElement !== editableDiv) {
            editableDiv.innerHTML = doc.data().text || "";
          }
        });

        const access = sessionStorage.getItem("sharedAccess");
        const correctPassword = "123"; // 🔐 Your chosen password

        if (access === "granted") {
          // Already unlocked
          editableDiv.contentEditable = "true";
          editableDiv.oninput = () => {
            docRef.set({ text: editableDiv.innerHTML });
          };

        } else if (access === "denied") {
          // Already failed earlier — skip prompt
          editableDiv.contentEditable = "false";
          alert("Shared notes are view-only for this session.");

        } else {
          // First time — ask for password
          const password = prompt("Enter password to edit shared notes (leave blank or incorrect to view only):");

          if (password === correctPassword) {
            sessionStorage.setItem("sharedAccess", "granted");
            editableDiv.contentEditable = "true";
            editableDiv.oninput = () => {
              docRef.set({ text: editableDiv.innerHTML });
            };
          } else {
            sessionStorage.setItem("sharedAccess", "denied");
            editableDiv.contentEditable = "false";
            alert("Incorrect password. Shared notes are view-only for this session.");
          }
        }
      }



      

      function loadPersonal() {
        const saved = localStorage.getItem("personalText");
        if (saved) editableDiv.innerHTML = saved;

        if (unsubscribe) unsubscribe(); // stop listening to Firestore

        editableDiv.contentEditable = "true";
        
        editableDiv.oninput = () => {
          localStorage.setItem("personalText", editableDiv.innerHTML);
        };
      }

      // Set initial mode
      window.onload = () => {
        const mode = localStorage.getItem("noteMode") || "shared";
        toggle.checked = mode === "shared";

        if (mode === "shared") {
          loadShared();
        } else {
          loadPersonal();
        }
      };

      toggle.onchange = () => {
        const newMode = toggle.checked ? "shared" : "personal";
        localStorage.setItem("noteMode", newMode);

        if (newMode === "shared") {
          loadShared();
        } else {
          loadPersonal();
        }
      };
    </script>
    """

    # Inject sidebar code into HTML file
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
        html = html.replace("<head>", "<head>\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">")

    if sidebar_code not in html:
        html = html.replace("</body>", sidebar_code + "\n</body>")

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
