"""
Lambda function to retrieve complete Purchase Order data from SAP
"""
import json
import os
import boto3
import urllib.parse
import urllib.request
import base64
from typing import Dict, Any

def get_sap_credentials():
    """Retrieve SAP credentials from Secrets Manager"""
    secret_arn = os.environ['SECRET_ARN']

    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager')

    response = client.get_secret_value(SecretId=secret_arn)
    secret = json.loads(response['SecretString'])

    return secret['SAP_HOST'], secret['SAP_USER'], secret['SAP_PASSWORD']

def build_sap_url(path: str, params: Dict[str, Any]) -> str:
    """Build SAP OData URL with parameters"""
    host, _, _ = get_sap_credentials()
    safe_chars = "'() "
    query_string = urllib.parse.urlencode(params, safe=safe_chars)
    return f'https://{host}{path}?{query_string}'

def call_sap_api(url: str) -> Dict[str, Any]:
    """Make authenticated call to SAP OData API"""
    _, user, password = get_sap_credentials()

    # Create basic auth header
    credentials = f'{user}:{password}'
    encoded_credentials = base64.b64encode(credentials.encode()).decode()

    headers = {
        'Authorization': f'Basic {encoded_credentials}',
        'Accept': 'application/json'
    }

    request = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else str(e)
        raise Exception(f"SAP API Error {e.code}: {error_body}")

def lambda_handler(event, context):
    """
    Lambda handler for get_complete_po_data tool

    Expected event format:
    {
        "po_number": "4500000520"
    }
    """
    try:
        # Extract PO number from event
        po_number = event.get('po_number')

        if not po_number:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'po_number is required'
                })
            }

        # Build URL for PO header with item expansion
        path = f"/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrder('{po_number}')"
        params = {
            '$expand': 'to_PurchaseOrderItem',
            '$format': 'json'
        }

        url = build_sap_url(path, params)

        # Call SAP API
        response_data = call_sap_api(url)

        # Extract and format the data
        po_data = response_data.get('d', {})

        # Format header
        header = {
            'PurchaseOrder': po_data.get('PurchaseOrder', ''),
            'CreationDate': po_data.get('CreationDate', ''),
            'PurchaseOrderDate': po_data.get('PurchaseOrderDate', ''),
            'CompanyCode': po_data.get('CompanyCode', ''),
            'PurchasingOrganization': po_data.get('PurchasingOrganization', ''),
            'PurchasingGroup': po_data.get('PurchasingGroup', ''),
            'Supplier': po_data.get('Supplier', ''),
            'DocumentCurrency': po_data.get('DocumentCurrency', ''),
            'Name': po_data.get('SupplierName', '')
        }

        # Format items
        items = []
        item_data = po_data.get('to_PurchaseOrderItem', {}).get('results', [])

        for item in item_data:
            items.append({
                'item': int(item.get('PurchaseOrderItem', 0)),
                'material': item.get('Material', ''),
                'name': item.get('PurchaseOrderItemText', ''),
                'qty': float(item.get('OrderQuantity', 0)),
                'uom': item.get('PurchaseOrderQuantityUnit', ''),
                'price': float(item.get('NetPriceAmount', 0)),
                'currency': item.get('DocumentCurrency', ''),
                'delivery_date': item.get('ScheduleLineDeliveryDate', ''),
                'plant': item.get('Plant', ''),
                'storage_location': item.get('StorageLocation', '')
            })

        # Calculate total
        total_value = sum(item['qty'] * item['price'] for item in items)

        result = {
            'purchase_order': po_number,
            'header': header,
            'items': items,
            'summary': {
                'total_items': len(items),
                'total_value': round(total_value, 2),
                'currency': header.get('DocumentCurrency', 'USD')
            }
        }

        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
