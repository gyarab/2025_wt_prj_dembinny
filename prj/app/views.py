from django.shortcuts import render

# Create your views here.
def render_home(req):
    return render(req, 'home.html')

def render_about(req):
    return render(req, 'about.html')