import gradio as gr
import aiohttp
import asyncio
import json
import logging
import os
import re
from PyPDF2 import PdfReader

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Nebius AI Studio setup
NEBIUS_API_TOKEN = os.getenv("NEBIUS_API_TOKEN", "eyJhbGciOiJIUzI1NiIsImtpZCI6IlV6SXJWd1h0dnprLVRvdzlLZWstc0M1akptWXBvX1VaVkxUZlpnMDRlOFUiLCJ0eXAiOiJKV1QifQ.eyJzdWIiOiJnb29nbGUtb2F1dGgyfDExNTI0NTkyNDY0MTk0ODI1NzEyOSIsInNjb3BlIjoib3BlbmlkIG9mZmxpbmVfYWNjZXNzIiwiaXNzIjoiYXBpX2tleV9pc3N1ZXIiLCJhdWQiOlsiaHR0cHM6Ly9uZWJpdXMtaW5mZXJlbmNlLmV1LmF1dGgwLmNvbS9hcGkvdjIvIl0sImV4cCI6MTkwNzE0NTgwMSwidXVpZCI6IjlkMDQ2YWM2LTU2OWUtNDFkYS1iYTg3LTA3Yzc2YTA0MmIwYSIsIm5hbWUiOiJhaWxhd3llcjIiLCJleHBpcmVzX2F0IjoiMjAzMC0wNi0wOFQxMTo0MzoyMSswMDAwIn0.goS3ZNUB8MTwxX6FVrvL9Ei_IbTaseMO4WcunDhxsis")
NEBIUS_API_URL = "https://api.studio.nebius.ai/v1/completions"

async def call_nebius(prompt: str, max_tokens: int = 2000):
    headers = {
        "Authorization": f"Bearer eyJhbGciOiJIUzI1NiIsImtpZCI6IlV6SXJWd1h0dnprLVRvdzlLZWstc0M1akptWXBvX1VaVkxUZlpnMDRlOFUiLCJ0eXAiOiJKV1QifQ.eyJzdWIiOiJnb29nbGUtb2F1dGgyfDExNTI0NTkyNDY0MTk0ODI1NzEyOSIsInNjb3BlIjoib3BlbmlkIG9mZmxpbmVfYWNjZXNzIiwiaXNzIjoiYXBpX2tleV9pc3N1ZXIiLCJhdWQiOlsiaHR0cHM6Ly9uZWJpdXMtaW5mZXJlbmNlLmV1LmF1dGgwLmNvbS9hcGkvdjIvIl0sImV4cCI6MTkwNzE0NTgwMSwidXVpZCI6IjlkMDQ2YWM2LTU2OWUtNDFkYS1iYTg3LTA3Yzc2YTA0MmIwYSIsIm5hbWUiOiJhaWxhd3llcjIiLCJleHBpcmVzX2F0IjoiMjAzMC0wNi0wOFQxMDo0MzoyMSswMDAwIn0.goS3ZNUB8MTwxX6FVrvL9Ei_IbTaseMO4WcunDhxsis",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "meta-llama/Meta-Llama-3.1-70B-Instruct",
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": 0.7
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(NEBIUS_API_URL, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    text = result.get("choices", [{}])[0].get("text", "").strip()
                    logger.debug(f"Nebius response: {text}")
                    return text
                else:
                    error_text = await resp.text()
                    logger.error(f"Nebius API error: {resp.status} - {error_text}")
                    return ""
        except Exception as e:
            logger.error(f"Nebius API request failed: {e}")
            return ""

def extract_text_from_file(file_path):
    """Extract text from text or PDF files."""
    try:
        if file_path.endswith(".pdf"):
            with open(file_path, "rb") as file:
                pdf = PdfReader(file)
                text = "".join(page.extract_text() for page in pdf.pages if page.extract_text())
                return text[:5000]  # Limit to 5000 chars
        elif file_path.endswith(".txt"):
            with open(file_path, "r", encoding="utf-8") as file:
                return file.read()[:5000]
        else:
            return "Unsupported file format. Please upload a .txt or .pdf file."
    except Exception as e:
        logger.error(f"Error extracting text from file: {e}")
        return f"Error reading file: {str(e)}"

async def run_legal_query(query: str, jurisdiction: str, contract: str, file):
    try:
        # Use uploaded file if provided, else use contract text
        contract_text = contract
        if file:
            contract_text = extract_text_from_file(file.name)
            if contract_text.startswith("Error") or contract_text.startswith("Unsupported"):
                return contract_text + "\n\n*Disclaimer: For informational purposes only, not legal advice.*"

        # Parse query with stricter JSON prompt
        prompt = f"""
        You are an AI lawyer assistant. Parse the user's query to identify the primary intent:
        - 'statute': Fetch a statute for a jurisdiction and topic.
        - 'contract': Analyze a contract.
        - 'document': Generate a legal document.
        If unclear, default to 'statute'. Extract the topic from the query or use 'general'.
        Query: "{query}"
        Jurisdiction: "{jurisdiction}"
        Contract: "{contract_text[:100]}"  # Truncate for prompt
        Output a JSON object with 'intent' and 'topic', ensuring property names are double-quoted.
        Example: {{"intent": "statute", "topic": "contract"}}
        Return only the JSON object, no extra text or formatting.
        """
        llm_response = await call_nebius(prompt, max_tokens=2000)
        logger.debug(f"LLM response: {llm_response}")

        # Parse JSON with robust fallback
        intent_data = {"intent": "statute", "topic": "general"}
        try:
            # Clean response by removing code blocks, prefixes, and extra whitespace
            cleaned_response = llm_response.strip()
            cleaned_response = re.sub(r'```[a-zA-Z]*\n?', '', cleaned_response)
            cleaned_response = re.sub(r'```', '', cleaned_response)
            cleaned_response = re.sub(r'^(Output|Response|Result):\s*', '', cleaned_response, flags=re.IGNORECASE)
            cleaned_response = cleaned_response.strip()
            
            # Try parsing as-is first
            intent_data = json.loads(cleaned_response)
        except json.JSONDecodeError:
            try:
                # Extract JSON object from response
                json_match = re.search(r'\{[^{}]*\}', cleaned_response)
                if json_match:
                    json_str = json_match.group()
                    # Fix common JSON issues: unquoted keys and single quotes
                    json_str = re.sub(r"(\w+):", r'"\1":', json_str)
                    json_str = json_str.replace("'", '"')
                    intent_data = json.loads(json_str)
                else:
                    # Extract intent and topic using regex as last resort
                    intent_match = re.search(r'"?intent"?\s*:\s*"?(\w+)"?', cleaned_response, re.IGNORECASE)
                    topic_match = re.search(r'"?topic"?\s*:\s*"?([^",}\n]+)"?', cleaned_response, re.IGNORECASE)
                    
                    if intent_match:
                        intent_data["intent"] = intent_match.group(1).strip()
                    if topic_match:
                        intent_data["topic"] = topic_match.group(1).strip()
                        
                    logger.info(f"Extracted intent: {intent_data['intent']}, topic: {intent_data['topic']}")
            except (json.JSONDecodeError, AttributeError) as e:
                logger.warning(f"Failed to parse LLM response, using defaults. Response: {llm_response[:200]}...")

        intent = intent_data.get("intent", "statute")
        topic = intent_data.get("topic", "general")

        async with aiohttp.ClientSession() as session:
            if intent == "statute":
                async with session.get(f"http://127.0.0.1:7860/fetch_statute?jurisdiction={jurisdiction}&topic={topic}") as resp:
                    result = (await resp.json()).get("result", "Error fetching statute")
            elif intent == "contract":
                async with session.post("http://127.0.0.1:7860/analyze_contract", json={"contract_text": contract_text}) as resp:
                    analysis = await resp.json()
                    result = f"Clauses: {analysis.get('key_clauses', [])}; Risks: {analysis.get('risks', [])}"
            else:
                details = {"query": query, "jurisdiction": jurisdiction, "contract": contract_text}
                async with session.post("http://127.0.0.1:7860/generate_document", json={"document_type": "Legal Opinion", "details": details}) as resp:
                    result = (await resp.json()).get("result", "Error generating document")
            logger.info(f"Final result: {result[:200]}...")  # Log first 200 chars of result
            return result
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return f"Error: {str(e)}\n\n*Disclaimer: For informational purposes only, not legal advice.*"

def main():
    custom_css = """
    :root {
        --primary-color: #3b82f6;
        --secondary-color: #1e40af;
        --accent-color: #10b981;
        --warning-color: #f59e0b;
        --danger-color: #ef4444;
        --dark-bg: #0f172a;
        --darker-bg: #020617;
        --card-bg: #1e293b;
        --border-color: #334155;
        --text-primary: #f1f5f9;
        --text-secondary: #cbd5e1;
        --input-bg: #334155;
        --hover-bg: #475569;
    }
    
    .gradio-container {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        min-height: 100vh;
        color: var(--text-primary);
    }
    
    .main-container {
        max-width: 1400px;
        margin: 0 auto;
        padding: 20px;
        background: var(--card-bg);
        border-radius: 20px;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        margin-top: 20px;
        margin-bottom: 20px;
        border: 1px solid var(--border-color);
    }
    
    .title-header {
        background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
        color: white;
        padding: 30px;
        border-radius: 15px;
        margin-bottom: 30px;
        text-align: center;
        box-shadow: 0 10px 25px rgba(59, 130, 246, 0.3);
    }
    
    .input-section {
        background: var(--dark-bg);
        padding: 25px;
        border-radius: 15px;
        border: 2px solid var(--border-color);
        margin-bottom: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    }
    
    .response-box {
        max-height: 500px;
        overflow-y: auto;
        border: 2px solid var(--accent-color);
        border-radius: 15px;
        padding: 20px;
        background: var(--input-bg);
        box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.2);
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        color: var(--text-primary);
    }
    
    .footer-disclaimer {
        background: linear-gradient(135deg, var(--warning-color) 0%, #f97316 100%);
        color: white;
        text-align: center;
        margin-top: 30px;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 8px 20px rgba(245, 158, 11, 0.3);
        font-weight: 500;
    }
    
    .tab-nav {
        background: var(--input-bg);
        border-radius: 10px;
        padding: 5px;
        border: 1px solid var(--border-color);
    }
    
    .examples-section {
        background: var(--dark-bg);
        border: 2px solid var(--border-color);
        border-radius: 15px;
        padding: 20px;
        margin-top: 15px;
        color: var(--text-primary);
    }
    
    /* Button Styling */
    .primary-button {
        background: linear-gradient(135deg, var(--accent-color) 0%, #059669 100%);
        border: none;
        color: white;
        padding: 12px 30px;
        border-radius: 10px;
        font-weight: 600;
        box-shadow: 0 4px 15px rgba(16, 185, 129, 0.4);
        transition: all 0.3s ease;
    }
    
    .primary-button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(16, 185, 129, 0.5);
    }
    
    .secondary-button {
        background: linear-gradient(135deg, var(--border-color) 0%, var(--hover-bg) 100%);
        border: none;
        color: var(--text-primary);
        padding: 12px 30px;
        border-radius: 10px;
        font-weight: 600;
        box-shadow: 0 4px 15px rgba(51, 65, 85, 0.3);
    }
    
    .secondary-button:hover {
        background: linear-gradient(135deg, var(--hover-bg) 0%, var(--border-color) 100%);
    }
    
    /* Input Styling */
    .gradio-textbox {
        background: var(--input-bg);
        border: 2px solid var(--border-color);
        border-radius: 10px;
        padding: 15px;
        transition: border-color 0.3s ease;
        color: var(--text-primary);
    }
    
    .gradio-textbox:focus {
        border-color: var(--primary-color);
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
    }
    
    /* File Upload Styling */
    .file-upload {
        border: 2px dashed var(--border-color);
        border-radius: 15px;
        padding: 30px;
        background: var(--input-bg);
        text-align: center;
        transition: all 0.3s ease;
        color: var(--text-primary);
    }
    
    .file-upload:hover {
        border-color: var(--primary-color);
        background: var(--hover-bg);
    }
    
    /* Dark theme text adjustments */
    label {
        color: var(--text-primary) !important;
    }
    
    .markdown {
        color: var(--text-primary) !important;
    }
    
    .gr-form {
        background: var(--input-bg);
        border: 1px solid var(--border-color);
    }
    """

    with gr.Blocks(theme=gr.themes.Soft(), css=custom_css, title="AI Lawyer Assistant") as demo:
        with gr.Column(elem_classes=["main-container"]):
            gr.Markdown(
                """
                # ⚖️ AI Lawyer Assistant
                
                **Professional Legal Research & Document Analysis Tool**
                
                Get instant legal insights, analyze contracts, and research statutes across different jurisdictions.
                """,
                elem_classes=["title-header"]
            )
            
            with gr.Row():
                with gr.Column(scale=2):
                    with gr.Group(elem_classes=["input-section"]):
                        gr.Markdown("### 📝 Query Information")
                        query = gr.Textbox(
                            label="Legal Query", 
                            placeholder="e.g., What are property laws in Texas? or Analyze this employment contract",
                            value="What are property laws in Texas?",
                            lines=2,
                            elem_classes=["gradio-textbox"]
                        )
                        
                        with gr.Row():
                            jurisdiction = gr.Textbox(
                                label="Jurisdiction", 
                                placeholder="e.g., Texas, California, UK, India",
                                value="Texas",
                                info="Specify the legal jurisdiction",
                                elem_classes=["gradio-textbox"]
                            )
                    
                    with gr.Group(elem_classes=["input-section"]):
                        gr.Markdown("### 📄 Document Input")
                        with gr.Tab("Upload File", elem_classes=["tab-nav"]):
                            file_upload = gr.File(
                                label="Upload Document", 
                                file_types=[".txt", ".pdf"],
                                elem_classes=["file-upload"]
                            )
                        
                        with gr.Tab("Paste Text", elem_classes=["tab-nav"]):
                            contract = gr.Textbox(
                                label="Contract/Document Text", 
                                lines=6,
                                placeholder="Paste your contract or legal document text here...",
                                elem_classes=["gradio-textbox"]
                            )
                    
                    with gr.Row():
                        submit = gr.Button("🔍 Analyze Legal Query", variant="primary", size="lg", elem_classes=["primary-button"])
                        clear = gr.Button("🗑️ Clear", variant="secondary", elem_classes=["secondary-button"])
                
                with gr.Column(scale=3):
                    gr.Markdown("### 📋 Legal Analysis Results")
                    output = gr.Textbox(
                        label="Legal Response", 
                        lines=20,
                        max_lines=25,
                        elem_classes=["response-box"],
                        show_copy_button=True,
                    )
                    
                    with gr.Accordion("📚 Example Queries", open=False, elem_classes=["examples-section"]):
                        gr.Markdown("""
                        **Statute Research:**
                        - "What are employment laws in California?"
                        - "Property rights in New York"
                        
                        **Contract Analysis:**
                        - "Analyze this employment contract" (with uploaded file)
                        - "Review this lease agreement"
                        
                        **Document Generation:**
                        - "Generate a legal opinion on intellectual property"
                        - "Create a contract template"
                        """)
            
            gr.Markdown(
                """
                ### ⚠️ Important Legal Disclaimer
                This AI tool provides **informational content only** and is **not a substitute for professional legal advice**. 
                Always consult with a qualified attorney for specific legal matters.
                """,
                elem_classes=["footer-disclaimer"]
            )
            
            # Event handlers
            submit.click(
                run_legal_query, 
                inputs=[query, jurisdiction, contract, file_upload], 
                outputs=output
            )
            
            def clear_all():
                return "", "Texas", "", None, ""
            
            clear.click(
                clear_all,
                outputs=[query, jurisdiction, contract, file_upload, output]
            )

    demo.launch(server_port=7861, share=False, server_name="127.0.0.1")

if __name__ == "__main__":
    main()