from django.shortcuts import render
import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from core.models import CodeExecution, CodeSnippet
from django.contrib.auth.models import User
from django.utils import timezone

def home_page(request):
    """
    View function for the home page of the site.
    """
    # You can add context data to pass to the template here
    context = {}
    
    # Render the HTML template home.html with the data in the context
    return render(request, 'home.html', context)

@csrf_exempt
def execute_code(request):
    """Execute code using Piston API and return the output"""
    if request.method == 'POST':
        try:
            # Get code data from request
            data = json.loads(request.body)
            code = data.get('code', '')
            language = data.get('language', 'cpp')
            user_input = data.get('input', '')
            snippet_id = data.get('snippet_id')
            
            # Get code snippet if ID is provided
            code_snippet = None
            if snippet_id:
                try:
                    code_snippet = CodeSnippet.objects.get(id=snippet_id)
                except CodeSnippet.DoesNotExist:
                    pass
            
            # Map Django language names to Piston API language identifiers
            language_map = {
                'cpp': 'cpp',
                'python': 'python3',
                'javascript': 'nodejs',
                'java': 'java'
            }
            piston_language = language_map.get(language, language)
            
            # Map file names based on language
            file_name_map = {
                'cpp': 'main.cpp',
                'python3': 'main.py',
                'nodejs': 'main.js',
                'java': 'Main.java'
            }
            file_name = file_name_map.get(piston_language, f'main.{language}')
            
            # For Java, extract the public class name and use it as the file name
            if piston_language == 'java':
                import re
                public_class_match = re.search(r'public\s+class\s+(\w+)', code)
                if public_class_match:
                    class_name = public_class_match.group(1)
                    file_name = f'{class_name}.java'
            
            # Prepare the Piston API request
            url = "https://emkc.org/api/v2/piston/execute"
            payload = {
                "language": piston_language,
                "version": "*",
                "files": [
                    { "name": file_name, "content": code }
                ],
                "stdin": user_input
            }
            headers = {"Content-Type": "application/json"}
            
            # Send the API request
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            result = response.json()
            
            # Extract output from response
            run = result.get("run", {})
            output = run.get("output", "No output generated")
            stderr = run.get("stderr", "")
            exit_code = run.get("code", 1)
            
            # Determine execution status
            execution_status = 'SUCCESS' if exit_code == 0 else 'ERROR'
            
            # Always save the code execution, even for anonymous users
            if not code_snippet and request.user.is_authenticated:
                # Create a temporary snippet if user is logged in but no snippet was specified
                code_snippet = CodeSnippet.objects.create(
                    title=f"Temporary Execution - {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    language=language,
                    owner=request.user,
                    code_content=code
                )
            
            if code_snippet:
                CodeExecution.objects.create(
                    code=code_snippet,
                    code_snapshot=code,
                    execution_result=output,
                    execution_status=execution_status
                )
            
            return JsonResponse({
                'status': 'success',
                'output': output,
                'stderr': stderr
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
