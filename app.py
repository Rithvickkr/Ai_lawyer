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
        - 'general': Provide general legal information.
        - 'guide': Provide a legal guide or overview.
        If unclear, default to 'statute'. Extract the topic from the query or use 'general'.
        Query: "{query}"
        Jurisdiction: "{jurisdiction}"
        Contract: "{contract_text[:500]}"  # Truncate for prompt
        Output a JSON object with 'intent' and 'topic', ensuring property names are double-quoted.
        Example: {{"intent": "statute", "topic": "contract"}}
        Return only the JSON object, no extra text or formatting.
        """
        llm_response = await call_nebius(prompt, max_tokens=5000)
        logger.debug(f"LLM response: {llm_response}")

        # Parse JSON with robust fallback
        intent_data = {"intent": "statute", "topic": "general",}
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

        # Generate response directly using Nebius AI instead of local endpoints
        if intent == "statute":
            final_prompt = f"""You are a legal expert. Provide information about {topic} laws in {jurisdiction}. 
            Include relevant statutes, key provisions, and practical implications. 
            Be comprehensive but concise. Format your response clearly with headings and bullet points where appropriate.
            
            Query: {query}
            Jurisdiction: {jurisdiction}
            Topic: {topic}"""
        elif intent == "contract":
            final_prompt = f"""You are a contract law expert. Analyze the following contract text and provide:
            1. Key clauses and their implications
            2. Potential risks and red flags
            3. Recommendations for improvements
            4. Compliance considerations
            
            Contract text: {contract_text[:3000]}
            
            Provide a detailed analysis with clear sections."""
        elif intent == "guide":
            final_prompt = f"""You are a legal guide expert. Based on the following query, guide the user through the legal topic:
            Query: {query}
            Jurisdiction: {jurisdiction}
            Context: {contract_text[:1000] if contract_text else 'No additional context provided'}
            Provide a structured guide with key points, relevant laws, and practical advice."""
        else:  # document generation
            final_prompt = f"""You are a legal document expert. Based on the following query, generate a comprehensive legal opinion or document:
            
            Query: {query}
            Jurisdiction: {jurisdiction}
            Context: {contract_text[:1000] if contract_text else 'No additional context provided'}
            
            Provide a well-structured legal document with appropriate sections, legal reasoning, and citations where relevant."""
        
        result = await call_nebius(final_prompt, max_tokens=3000)
        if not result:
            result = "I apologize, but I'm unable to process your request at this time. Please try again later or rephrase your query."
        
        logger.info(f"Final result: {result[:200]}...")  # Log first 200 chars of result
        def format_response_markdown(text: str) -> str:
            """Format the response text with clean, readable structure."""
            if not text or text.strip() == "":
                return "No relevant information found. Please try a different query or check the input text."
            
            # Clean up the text
            text = text.strip()
            
            # Remove excessive whitespace and normalize line endings
            text = re.sub(r'\r\n|\r', '\n', text)
            text = re.sub(r'[ \t]+', ' ', text)
            text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
            
            # Remove any existing markdown/HTML formatting that might be malformed
            text = re.sub(r'<[^>]+>', '', text)
            text = re.sub(r'\*{2,}', '', text)
            
            # Format headers (lines that end with colon or are followed by content)
            text = re.sub(r'\n([A-Z][A-Za-z\s]{3,}):?\n(?=[A-Za-z])', r'\n\n**\1**\n', text)
            
            # Format numbered sections
            text = re.sub(r'\n(\d+\.\s+[A-Z][^:\n]*):?\n', r'\n\n**\1**\n', text)
            
            # Format bullet points consistently
            text = re.sub(r'\n\s*[-•*]\s*', r'\n• ', text)
            
            # Format sub-bullets with proper indentation
            text = re.sub(r'\n\s+[-•*]\s*', r'\n  - ', text)
            
            # Clean up any double formatting
            text = re.sub(r'\*\*\*+([^*]+)\*\*\*+', r'**\1**', text)
            
            # Ensure proper spacing around headers
            text = re.sub(r'\n\*\*([^*]+)\*\*\n(?=[A-Za-z])', r'\n\n**\1**\n\n', text)
            
            # Clean up final formatting
            text = re.sub(r'\n{3,}', '\n\n', text)
            
            return text.strip()

        # Format the result before returning
        result = format_response_markdown(result)
        return result + "\n\n*Disclaimer: For informational purposes only, not legal advice.*"
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return f"Error: {str(e)}\n\n*Disclaimer: For informational purposes only, not legal advice.*"

def main():
    custom_css = """
    :root {
        --primary-bg-start: #1E1F2B;
        --primary-bg-end: #20212E;
        --card-bg: #2B2C3B;
        --primary-accent-start: #1E90FF;
        --primary-accent-end: #4F9CFF;
        --text-color: #E0E0E0;
        --cta-color: #00C781;
        --warning-color: #FFA500;
        --border-color: #3A3B4C;
        --hover-bg: #353648;
        --input-bg: #252636;
        --shadow-color: rgba(0, 0, 0, 0.25);
        --highlight-color: #A78BFA;
    }
    
    .gradio-container {
        background: linear-gradient(135deg, var(--primary-bg-start) 0%, var(--primary-bg-end) 100%);
        min-height: 100vh;
        color: var(--text-color);
        font-family: 'Inter', 'Roboto', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    .main-container {
        max-width: 1400px;
        margin: 0 auto;
        padding: 24px;
        background: var(--card-bg);
        border-radius: 16px;
        box-shadow: 0 20px 40px var(--shadow-color);
        margin-top: 24px;
        margin-bottom: 24px;
        border: 1px solid var(--border-color);
    }
    
    .title-header {
        background: linear-gradient(135deg, var(--primary-accent-start) 0%, var(--primary-accent-end) 100%);
        color: white;
        padding: 32px;
        border-radius: 12px;
        margin-bottom: 32px;
        text-align: center;
        box-shadow: 0 12px 28px rgba(30, 144, 255, 0.3);
        font-weight: 700;
        font-size: 24px;
    }
    
    .input-section {
        background: var(--card-bg);
        padding: 24px;
        border-radius: 12px;
        border: 1px solid var(--border-color);
        margin-bottom: 24px;
        box-shadow: 0 4px 12px var(--shadow-color);
    }
    
    .input-section h3 {
        color: var(--text-color);
        font-weight: 600;
        font-size: 16px;
        margin-bottom: 16px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .response-box {
        max-height: 500px;
        overflow-y: auto;
        border: 2px solid var(--cta-color);
        border-radius: 12px;
        padding: 20px;
        background: var(--input-bg);
        box-shadow: inset 0 2px 6px rgba(0, 0, 0, 0.2);
        font-family: 'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        color: var(--text-color);
        font-size: 14px;
        line-height: 1.6;
    }
    
    .footer-disclaimer {
        background: linear-gradient(135deg, var(--warning-color) 0%, #FF8C00 100%);
        color: white;
        text-align: center;
        margin-top: 32px;
        padding: 24px;
        border-radius: 12px;
        box-shadow: 0 8px 20px rgba(255, 165, 0, 0.3);
        font-weight: 500;
        font-size: 14px;
    }
    
    .tab-nav {
        background: var(--input-bg);
        border-radius: 8px;
        padding: 8px;
        border: 1px solid var(--border-color);
    }
    
    .examples-section {
        background: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 20px;
        margin-top: 16px;
        color: var(--text-color);
        box-shadow: 0 4px 12px var(--shadow-color);
    }
    
    /* Button Styling */
    .primary-button {
        background: linear-gradient(135deg, var(--cta-color) 0%, #00A86B 100%);
        border: none;
        color: white;
        padding: 14px 32px;
        border-radius: 10px;
        font-weight: 700;
        font-size: 14px;
        box-shadow: 0 6px 18px rgba(0, 199, 129, 0.4);
        transition: all 0.3s ease;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .primary-button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(0, 199, 129, 0.5);
        filter: brightness(110%);
    }
    
    .secondary-button {
        background: linear-gradient(135deg, var(--border-color) 0%, var(--hover-bg) 100%);
        border: none;
        color: var(--text-color);
        padding: 14px 32px;
        border-radius: 10px;
        font-weight: 600;
        font-size: 14px;
        box-shadow: 0 4px 12px rgba(58, 59, 76, 0.3);
        transition: all 0.3s ease;
    }
    
    .secondary-button:hover {
        background: linear-gradient(135deg, var(--hover-bg) 0%, var(--border-color) 100%);
        filter: brightness(110%);
    }
    
    /* Input Styling */
    .gradio-textbox {
        background: var(--input-bg);
        border: 2px solid var(--border-color);
        border-radius: 8px;
        padding: 16px;
        transition: all 0.3s ease;
        color: var(--text-color);
        font-size: 14px;
        font-weight: 400;
    }
    
    .gradio-textbox:focus {
        border-color: var(--primary-accent-start);
        box-shadow: 0 0 0 3px rgba(30, 144, 255, 0.2);
        outline: none;
    }
    
    /* File Upload Styling */
    .file-upload {
        border: 2px dashed var(--border-color);
        border-radius: 12px;
        padding: 32px;
        background: var(--input-bg);
        text-align: center;
        transition: all 0.3s ease;
        color: var(--text-color);
    }
    
    .file-upload:hover {
        border-color: var(--primary-accent-start);
        background: var(--hover-bg);
        box-shadow: 0 4px 12px rgba(30, 144, 255, 0.2);
    }
    
    /* Label and Text Styling */
    label {
        color: var(--text-color) !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .markdown {
        color: var(--text-color) !important;
        line-height: 1.6;
    }
    
    .gr-form {
        background: var(--input-bg);
        border: 1px solid var(--border-color);
        border-radius: 8px;
    }
    
    /* Highlight Tags */
    .highlight-tag {
        background: var(--highlight-color);
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
        margin: 2px;
    }
    
    /* Typography Enhancements */
    h1, h2, h3 {
        font-weight: 700;
        color: var(--text-color);
    }
    
    h1 { font-size: 28px; }
    h2 { font-size: 22px; }
    h3 { font-size: 18px; }
    
    p {
        font-size: 14px;
        font-weight: 400;
        line-height: 1.6;
        color: var(--text-color);
    }
    
    /* Professional spacing */
    .gr-group {
        gap: 24px;
    }
    
    .gr-row {
        gap: 16px;
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
                return "", "India", "", None, ""
            
            clear.click(
                clear_all,
                outputs=[query, jurisdiction, contract, file_upload, output]
            )

    demo.launch(server_port=7861, share=False, server_name="127.0.0.1")

if __name__ == "__main__":
    main()