import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db import connection
import subprocess
import socket
import re
import platform
from .models import AIConfiguration, ChatSession, ChatMessage, AIDataSkill

@csrf_exempt
@login_required
@require_POST
def chat_api(request):
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return JsonResponse({'error': 'Message is empty'}, status=400)
            
        # Get active AI config
        config = AIConfiguration.objects.filter(is_active=True).first()
        if not config:
            return JsonResponse({'error': 'AI Configuration is not set or inactive.'}, status=500)
            
        # Get or create the user's active session. 
        # For simplicity, we just use the most recent session or create one.
        session = ChatSession.objects.filter(user=request.user).order_by('-created_at').first()
        if not session:
            session = ChatSession.objects.create(user=request.user)
            
        # Save user message
        ChatMessage.objects.create(session=session, role='user', content=user_message)
        
        # Build message history for the API (Limit to last 10 messages to save context window)
        history = ChatMessage.objects.filter(session=session).order_by('-timestamp')[:10]
        # Reverse it so oldest is first
        history = reversed(list(history))
        
        # Build dynamic context based on user profile and ITMS app info
        user = request.user
        role_label = "Administrator (Full Access)" if user.is_superuser else "Staff / Employee"
        dept_name = user.department.name if getattr(user, 'department', None) else 'N/A'
        
        dynamic_context = f"""
--- APP CONTEXT ---
Application: ITMS Pro (IT Management System)
You are the IT Assistant for ITMS Pro. You act as a direct data shortcut to the application's database, NOT a tour guide.

--- USER CONTEXT ---
Name: {user.username}
Job Title: {getattr(user, 'job_title', 'Employee')}
Department: {dept_name}
Authority Level: {role_label}

--- STRICT RULES (ANTI-HALLUCINATION) ---
1. DIRECT SHORTCUT: Do NOT tell the user to "go to the menu" to find things. You must give them the direct answer or data.
2. If the system provides 'DYNAMIC DATA FOUND' below, present that data directly to the user in a nice Markdown table.
3. If the system says 'NO DATA' was found, simply reply: "Saat ini tidak ada data yang cocok dengan permintaan Anda di database."
4. CRITICAL: If the user asks for data/tables (like lists of assets, users, categories) and there is NO 'DYNAMIC DATA' section provided to you below, you MUST NOT invent or hallucinate data. You must reply honestly: "Maaf, saya belum memiliki skill atau akses untuk menarik data tersebut dari database."
"""

        # --- BUILT-IN NETWORK SKILLS ---
        network_context = ""
        user_msg_lower = user_message.lower()
        
        # Skill 1: Ping
        ping_match = re.search(r'ping\s+(?:ke\s+)?([a-zA-Z0-9.-]+)', user_msg_lower)
        if ping_match:
            target = ping_match.group(1)
            # Security: Allow only alphanumeric, dots, and hyphens
            if re.match(r'^[a-zA-Z0-9.-]+$', target):
                try:
                    param = '-n' if platform.system().lower() == 'windows' else '-c'
                    command = ['ping', param, '4', target]
                    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
                    network_context += f"\n--- DYNAMIC DATA FOUND FROM DATABASE ---\nThe system executed a PING command to {target}.\nData/Output:\n{result.stdout}\n\nPlease present this ping result to the user nicely and explain what it means (e.g., is the server up or down?).\n"
                except Exception as e:
                    network_context += f"\n--- DYNAMIC DATA CHECK ---\nPing command failed: {str(e)}\nPlease tell the user the ping failed.\n"
            else:
                network_context += f"\n--- DYNAMIC DATA CHECK ---\nTarget ping tidak valid.\nPlease tell the user the target is invalid.\n"
        
        # Skill 2: Port Check (Telnet/Socket)
        port_match = re.search(r'(?:cek\s+)?port\s+(\d+)\s+(?:di\s+|pada\s+)?([a-zA-Z0-9.-]+)', user_msg_lower)
        if port_match and not network_context:
            port = int(port_match.group(1))
            target = port_match.group(2)
            if re.match(r'^[a-zA-Z0-9.-]+$', target) and 1 <= port <= 65535:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(3)
                    res = sock.connect_ex((target, port))
                    sock.close()
                    status = "OPEN (Terbuka dan merespons)" if res == 0 else "CLOSED/FILTERED (Tertutup atau tidak merespons)"
                    network_context += f"\n--- DYNAMIC DATA FOUND FROM DATABASE ---\nThe system executed a PORT CHECK for {target} on port {port}.\nResult: Port is {status}.\n\nPlease tell the user the result.\n"
                except Exception as e:
                    network_context += f"\n--- DYNAMIC DATA CHECK ---\nPort check failed: {str(e)}\n"

        # Skill 3: Web Health Check (HTTP Status)
        web_match = re.search(r'cek\s+(?:web\s+|website\s+|portal\s+)?((?:https?://)?[a-zA-Z0-9.-]+)', user_msg_lower)
        if web_match and not network_context:
            url = web_match.group(1)
            if not url.startswith('http'):
                url = 'http://' + url
            try:
                web_resp = requests.get(url, timeout=5)
                network_context += f"\n--- DYNAMIC DATA FOUND FROM DATABASE ---\nThe system executed an HTTP GET request to {url}.\nStatus Code: {web_resp.status_code}\nReason: {web_resp.reason}\n\nPlease tell the user if the website is up or down based on this status code.\n"
            except Exception as e:
                 network_context += f"\n--- DYNAMIC DATA FOUND FROM DATABASE ---\nThe system executed an HTTP GET request to {url} but it FAILED.\nError: {str(e)}\n\nPlease tell the user that the website appears to be DOWN or unreachable.\n"

        if network_context:
            dynamic_context += network_context
        else:
            # Check for Dynamic AI Skills (SQL Execution)
            sql_context = ""
            active_skills = AIDataSkill.objects.filter(is_active=True)
            
            for skill in active_skills:
                keywords = [k.strip().lower() for k in skill.trigger_keywords.split(',')]
                if any(k in user_msg_lower for k in keywords if k):
                    # We found a matching skill!
                    query = skill.sql_query.strip()
                    # Safety check: block destructive keywords
                    destructive_words = ['delete ', 'update ', 'drop ', 'insert ', 'alter ', 'truncate ', 'grant ', 'revoke ']
                    query_lower = query.lower()
                    if any(bad_word in query_lower for bad_word in destructive_words):
                        sql_context += f"\n[WARNING: Skill '{skill.name}' contains forbidden SQL operations and was blocked.]"
                        continue
                    
                    try:
                        with connection.cursor() as cursor:
                            cursor.execute(query)
                            columns = [col[0] for col in cursor.description]
                            rows = cursor.fetchall()
                            
                            # Limit to 50 rows just in case
                            rows = rows[:50]
                            
                            if not rows:
                                sql_context += f"\n--- DYNAMIC DATA CHECK ---\nThe system checked the database for '{skill.name}' but found NO DATA (0 results).\nPlease tell the user that there is currently no data matching their request.\n"
                            else:
                                # Build string representation
                                data_str = f"Columns: {', '.join(columns)}\n"
                                for row in rows:
                                    data_str += " | ".join([str(val) for val in row]) + "\n"
                                    
                                sql_context += f"\n--- DYNAMIC DATA FOUND FROM DATABASE ---\nThe system executed a database query to help you answer the user.\nSkill Name: {skill.name}\nData:\n{data_str}\n\nPlease present this data to the user nicely (e.g., in a Markdown table or list) and answer their request.\n"
                    except Exception as e:
                        sql_context += f"\n[ERROR executing skill '{skill.name}': {str(e)}]\n"
                    
                    # Only execute the first matching skill to avoid overloading the prompt
                    break
                    
            if sql_context:
                dynamic_context += sql_context
        
        final_system_prompt = f"{config.system_prompt}\n\n{dynamic_context}"
        messages_payload = [
            {"role": "system", "content": final_system_prompt}
        ]
        
        for msg in history:
            messages_payload.append({
                "role": msg.role,
                "content": msg.content
            })
            
        # Call the local API
        headers = {
            "Content-Type": "application/json",
        }
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
            
        payload = {
            "model": config.model_name,
            "messages": messages_payload,
            "temperature": 0.7,
        }
        
        # We append /chat/completions to base_url if it doesn't already have it
        api_url = config.base_url
        if not api_url.endswith('/chat/completions'):
            api_url = api_url.rstrip('/') + '/chat/completions'
            
        try:
            # Meningkatkan timeout menjadi 90 detik karena AI lokal kadang butuh waktu lama untuk berpikir
            response = requests.post(api_url, headers=headers, json=payload, timeout=90)
            response.raise_for_status()
            response_data = response.json()
            
            assistant_reply = response_data['choices'][0]['message']['content']
            
            # Save assistant message
            ChatMessage.objects.create(session=session, role='assistant', content=assistant_reply)
            
            return JsonResponse({'reply': assistant_reply})
            
        except requests.exceptions.Timeout:
            return JsonResponse({'error': "Maaf, server AI sedang sibuk atau butuh waktu terlalu lama untuk berpikir (Timeout). Silakan coba lagi."}, status=400)
        except requests.exceptions.RequestException as e:
            return JsonResponse({'error': f"Gagal terhubung ke server AI: {str(e)}"}, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON format'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def clear_chat(request):
    # This creates a new session so the history starts fresh
    ChatSession.objects.create(user=request.user)
    return JsonResponse({'status': 'success'})

@login_required
def chat_history(request):
    session = ChatSession.objects.filter(user=request.user).order_by('-created_at').first()
    if not session:
        return JsonResponse({'messages': []})
        
    messages = ChatMessage.objects.filter(session=session).order_by('timestamp')
    msg_list = [{'role': m.role, 'content': m.content} for m in messages]
    return JsonResponse({'messages': msg_list})
