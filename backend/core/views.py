from rest_framework.decorators import api_view
from rest_framework.response import Response

# Create your views here.

@api_view(['GET'])
def api_root(request):
    """API根路径测试"""
    return Response({
        'status': 'success',
        'message': '产量监控预警系统API',
        'version': '1.0.0'
    })
