# Orbi Server
The Server for Orbi. Required for the Orbi Client. Doesn't need to be hosted on the same PC.

> [!WARNING]
> Orbi Server ("the software") is provided "as is" without warranties of any kind. We are not liable for any damages arising from its use, including the capture or misuse of screenshots containing sensitive information. The software may capture passwords, DRM-protected content, and copyrighted material.
>
> By using Orbi Server, you agree to comply with all applicable laws. Your use of the software is at your own risk. We do not warrant it will be error-free or free from harmful components.
>
> We are not affiliated with Microsoft. Orbi Server is licensed under AGPLv3. By downloading, installing, or using the software, you acknowledge that you have read, understood, and agree to this disclaimer.

## Setup
### Prerequisites:
- Windows 10/11
- Python 3.12
- A decent computer (It runs fine on my PC's RX 7600, but it will struggle on lower-end hardware.)
- Ollama (Download from https://ollama.com/ and run `ollama pull llama3:8b`. Make sure the server is running)
- [Tesseract](https://github.com/UB-Mannheim/tesseract/releases/latest)
### Setup:
1. `git clone https://github.com/OrbiAi/Orbi-Server` to clone the repository
2. `python -m venv .venv` to make a new venv
3. Activate the virtual environment:
    - For Command Prompt: `.\.venv\Scripts\activate`
    - For PowerShell: `.\.venv\Scripts\Activate.ps1`
4. Install the required packages:
    - `pip install -r requirements.txt`
5. Go through config.json.example and tweak the config to your needs, save as config.json
6. Start the Orbi Server:
    - `python main.py`

## License
This project is licensed under [AGPLv3](LICENSE).
