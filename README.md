# Writing Tools

### **Instantly proofread and optimize your writing system-wide with AI:**

https://github.com/user-attachments/assets/d3ce4694-b593-45ff-ae9a-892ce94b1dc8

### **Summarize content (webpages, YouTube videos, documents...) in a click:**

https://github.com/user-attachments/assets/76d13eb9-168e-4459-ada4-62e0586ae58c

### **Add your own buttons for unlimited potential!**

![image](https://github.com/user-attachments/assets/f5391035-56a4-4a4f-9078-aedec4244af6)

## ✨ What is Writing Tools?

Writing Tools is an **Apple Intelligence-inspired application for Windows and Linux that supercharges your writing with an AI LLM** (cloud-based or local).

With one hotkey press system-wide, it lets you fix grammar, optimize text according to your instructions, summarize content (webpages, YouTube videos, etc.), and more.

It's currently the **world's most intelligent system-wide grammar assistant**, works in ~any language, and has been featured in 🔥 [**30+ global publications**](docs/media-coverage.md) ([Beebom](https://beebom.com/high-schooler-app-brings-apple-inteligence-writing-tools-windows/), [XDA](https://www.xda-developers.com/windows-pc-can-now-deliver-instant-free-writing-help-across-all-apps/), [How-To Geek](https://www.howtogeek.com/if-you-like-apple-intelligences-writing-tool-try-this-open-source-app-as-its-windows-counterpart/), [Neowin](https://www.neowin.net/news/apple-intelligence-writing-tools-for-windows-get-new-summarization-features-and-more/), [Windows Central](https://www.windowscentral.com/software-apps/can-apple-catch-up-apple-intelligence-just-shipped-yet-free-apple-writing-tools-on-github-for-windows-and-linux-make-a-better-alternative)...).

Writing Tools was also among the 🔥 [**top 10 most trending AI programs in the world**](https://devface.ai/ranking/top_ai_developers/2024-10) on GitHub in October 2024.

---

Hi! I'm Jesai, a high school student from Bangalore, and I created and maintain Writing Tools with help from our [amazing contributors](https://github.com/theJayTea/WritingTools/edit/main/README.md#-contributors). I want to especially shout out [momokrono](https://github.com/momokrono), who's contributed extensively!

Writing Tools will always remain completely free and open-source.

If you find value in it, it would mean the world to me if you could support us as we continue to improve it. ❤️

<table>
  <tr>
    <td><b>Support Jesai</b> (Windows/Linux):</td>
  </tr>
  <tr>
    <td><a href="https://www.buymeacoffee.com/jesaitarun" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;"></a></td>
  </tr>
</table>

---

## ⚡ What can I do with Writing Tools, exactly?

### 1️⃣ Hyper-intelligent Writing Tools:
- Select _any_ text on your PC and invoke Writing Tools with `ctrl+space`.
- Choose **Proofread**, **Rewrite**, **Friendly**, **Professional**, **Concise**, or even enter **custom instructions** (e.g., _"add comments to this code"_, _"make it title case"_, _"translate to French"_).
- Your text will instantly be replaced with the AI-optimized version. Use `ctrl+z` to revert.

### 2️⃣ Powerful content summarization that you can chat with:
- Select all text in any webpage, document, email, etc., with `ctrl+a`, or select the transcript of a YouTube video (from its description).
- Choose **Summary**, **Key Points**, or **Table** after invoking Writing Tools.
- Get a pop-up summary with clear and beautiful formatting (with Markdown rendering), saving you hours.
- Chat with the summary if you'd like to learn more or have questions.

### 3️⃣ Go wild with your own buttons!
- They're your own magic buttons. Dream, and it'll magically be done with AI.

### 3️⃣ Chat with an LLM anytime in a click:
- Press `ctrl+space` without selecting text to start a conversation with your LLM _(for privacy, chat history is deleted when you close the window)_.

## 🌟 Why Choose Writing Tools?

Aside from being the only Windows/Linux program like Apple's Writing Tools:

- **More intelligent than Apple's Writing Tools and Grammarly Premium:** Apple uses a tiny 3B parameter model, while Writing Tools lets you use modern flagship models (e.g., Gemini Flash Latest, Gemini 3.8 Flash, Gemini 4, Gemma 4, GPT-6 Luna, GPT-5.4 Mini). Grammarly's rule-based NLP can't compete with LLMs.
- **Completely free and open-source:** No subscriptions or hidden costs. Bloat-free and uses **~0% of your CPU** even when actively using it.
- **Versatile AI LLM support:** Jump in quickly with the **Gemini API (Gemini Flash / Gemini 4 / Gemma 4)**, or **local LLMs via llama.cpp** (defaulting to **Gemma 4 E2B IT** [[instructions]](#llamacpp-local-llm-instructions)) as well as KoboldCPP, TabbyAPI, vLLM, or **cloud-based LLMs** (OpenAI, Mistral AI, OpenRouter, etc.) through Writing Tools' OpenAI-API-compatibility (all managed via `pydantic-ai`).
- **Does not mess with your clipboard, and works system-wide.**
- **Privacy-focused**: Your API key and config files stay on *your* device. NO logging, diagnostic collection, tracking, or ads. Invoked *only* on your command. Local LLMs keep your data on your device & work without the internet.
- **Supports multiple languages:** Works with any language and translates text better than Google Translate (type "translate to [language]" in `Describe your change...`).
- **Code support:** Fix, improve, translate, or add comments to code with `Describe your change...`."
- **Themes, Dark Mode, & Customization**: Choose between **2 themes**: a blurry gradient theme and a plain theme that resembles the Windows + V pop-up! Also has full **dark mode** support. **Set your own hotkey** for quick access.

## ✅ **1 Minute Installation**

### **🪟 Windows**:
1. Go to the [Releases](https://github.com/theJayTea/WritingTools/releases) page and download the latest `Writing.Tools.zip` file.
2. Extract it to your desired location (recommended: `Documents` or `App Data/Local`), run `Writing Tools.exe`, and enjoy! :D

*Note: Writing Tools is a portable app. If you extract it into a protected folder (e.g., Program Files), you must run it as administrator at least on first launch so it can create/edit its config files (in the same folder as its exe).*

**PS: Go to Writing Tools' Settings (from its tray icon at the bottom right of the taskbar) to enable starting Writing Tools on boot.**

### **🐧 Linux (work-in-progress)**:
[Run it from the source code](docs/running-from-source.md)

Writing Tools works well on x11. On Wayland, there are a few caveats:
- [it works on XWayland apps](https://github.com/theJayTea/WritingTools/issues/34#issuecomment-2461633556)
- [and it works if you disable Wayland for individual Flatpaks with Flatseal.](https://github.com/theJayTea/WritingTools/issues/93#issuecomment-2576511041)

---

## 👀 Tips

#### 1️⃣ Summarise a YouTube video from its transcript:

https://github.com/user-attachments/assets/dd4780d4-7cdb-4bdb-9a64-e93520ab61be

#### 2️⃣ Make Writing Tools work better in MS Word: the `ctrl+space` keyboard shortcut is mapped to "Clear Formatting", making you lose paragraph indentation. Here's how to improve this:
P.S.: Word's rich-text formatting (bold, italics, underline, colours...) will be lost on using Writing Tools. A Markdown editor such as [Obsidian](https://obsidian.md/) has no such issue.

https://github.com/user-attachments/assets/42a3d8c7-18ac-4282-9478-16aab935f35e

## 🔒 Privacy

I believe strongly in protecting your privacy. Writing Tools:
- Does not collect or store any of your writing data by itself. It doesn't even collect general logs, so it's super light and privacy-friendly.
- Lets you use local LLMs to process your text entirely on-device.
- Only sends text to the chosen AI provider (encrypted) when you *explicitly* use one of the options.
- Only stores your API key locally on your device.

Note: If you choose to use a cloud based LLM, refer to the AI provider's privacy policy and terms of service.

## ✨ Options Explained

- **Proofread:** The smartest grammar & spelling corrector. Sorry not sorry, Grammarly Premium.
- **Rewrite:** Improve the phrasing of your text.
- **Make Friendly/Professional:** Adjust the tone of your text.
- **Custom Instructions:** Tailor your request (e.g., "Translate to French") through `Describe your change...`.

The following options respond in a pop-up window (with markdown rendering, selectable text, and a zoom level that saves & applies on app restarts):
- **Summarize:** Create clear and concise summaries.
- **Extract Key Points:** Highlight the most important points.
- **Create Tables:** Convert text into a formatted table. PS: You can copy & paste the table into MS Word.

<a id="llamacpp-local-llm-instructions"></a>
## (Optional) llama.cpp Local LLM Instructions (Gemma 4 E2B IT)

Run Writing Tools completely offline and privately using `llama.cpp`'s built-in OpenAI-compatible server (`llama-server`) with Google's **Gemma 4 E2B IT** model:

1. Download or install [`llama.cpp`](https://github.com/ggml-org/llama.cpp/releases) (`llama-server`).
2. Start `llama-server` with Gemma 4 E2B IT directly from Hugging Face:
   ```bash
   llama-server -hf ggml-org/gemma-4-E2B-it-GGUF:Q4_K_M --port 8080 -ngl 99
   ```
   *(Use `-ngl 0` for CPU-only execution, or adjust `-c 32768` based on available RAM/VRAM.)*
3. Open Writing Tools Settings and select the **`llama.cpp (Local LLM)`** AI provider.
   - **Server Base URL**: `http://127.0.0.1:8080/v1` (default)
   - **Model**: `gemma-4-E2B-it` (default; or select `ggml-org/gemma-4-E2B-it-GGUF:Q4_K_M` / `gemma-4-E4B-it` / Custom)
   - **API Key**: Leave blank unless you started `llama-server` with `--api-key`
4. Save Settings and enjoy Writing Tools locally with zero cloud dependency.

## 🐞 Known Issues
1. Some reported hotkey conflicts on the latest v9 build: will release a maintenance update when I get time!

2. On some devices, Writing Tools does not work correctly with the default hotkey.
   
   To fix it, simply change the hotkey to **ctrl+`** or **ctrl+j** and restart Writing Tools. PS: If a hotkey is already in use by a program or background process, Writing Tools may not be able to intercept it. The above hotkeys are usually unused.

3. The initial launch of the `Writing Tools.exe` might take unusually long — this seems to be because AV software extensively scans this new executable before letting it run. Once it launches into the background in RAM, it works instantly as usual.

## 👨‍💻 To Run Writing Tools Directly from the Source Code

[Instructions here!](docs/running-from-source.md)


## 👨‍💻 To Compile the Application Yourself:

[Instructions here!](docs/building.md)

## 🌟 Contributors

Writing Tools would not be where it is today without its amazing contributors:

### 🪟🐧 Windows & Linux version:
**1. [momokrono](https://github.com/momokrono):**

Added Linux support, switched to the pynput API to improve Windows stability. Added Ollama API support, the core logic for customisable buttons, and localization. Fixed misc. bugs and added graceful termination support by handling SIGINT signal.

@momokrono has been incredibly kind and helpful, and I'm forever grateful to have him as a contributor. Not only has he provided extensive help with code, but he's also played a big role in managing GitHub issues. - Jesai

**2. [Cameron Redmore (CameronRedmore)](https://github.com/CameronRedmore):**

Extensively refactored Writing Tools and added OpenAI Compatible API support, streamed responses, and the chat mode when no text is selected.

**3. [Soszust40 (Soszust40)](https://github.com/Soszust40):**

Helped add dark mode, the plain theme, tray menu fixes, and UI improvements.

**4. [Alok Saboo (arsaboo)](https://github.com/arsaboo):**

Helped improve the reliability of text selection.

**5. [raghavdhingra24](https://github.com/raghavdhingra24):**

Made the rounded corners anti-aliased & prettier.

**6. [ErrorCatDev](https://github.com/ErrorCatDev):**

Significantly improved the About window, making it scrollable and cleaning things up. Also improved our .gitignore & requirements.txt.

**7. [Vadim Karpenko](https://github.com/Vadim-Karpenko):**

Helped add the start-on-boot setting!


## 🤝 Contributing

I welcome contributions! :D

If you'd like to improve Writing Tools, please feel free to open a Pull Request or get in touch with me (email below).

If there are major changes on your mind, it may be a good idea to get in touch before working on it.

## 📬 Contact

Email: jesaitarun@gmail.com

Made with ❤️ by a high school student. Check out my other app, [Bliss AI](https://play.google.com/store/apps/details?id=com.jesai.blissai), a free AI tutor!

## 📄 License

Distributed under the GNU General Public License v3.0.
