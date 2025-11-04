# SAP Agent - Quick Start Guide

Get started with the SAP Inventory Management Agent in 5 minutes!

## 🚀 Quick Access

### Test the Agent Now
```bash
python utils/test_e2e_agent.py
```

### Invoke the Agent Directly
```bash
python -c "
from utils.agent import invoke_agent
result = invoke_agent(
    'arn:aws:bedrock-agentcore:us-east-1:654537381132:runtime/strands_s3_hebinv_TST-AOSMpkAeu5',
    'מה המידע על הזמנת רכש 4500000520?'
)
print(result['response'])
"
```

---

## 📝 Top 10 Most Useful Questions

### 1. Get Purchase Order Details
```
מה המידע על הזמנת רכש 4500000520?
```
**What you'll get**: Complete PO information including header, all line items, supplier details, totals, and recommendations.

### 2. Check Item Count
```
כמה פריטים יש בהזמנת רכש 4500000520?
```
**What you'll get**: Number of items, detailed breakdown of each item with quantities and descriptions.

### 3. Get Total Value
```
מה הערך הכולל של הזמנת רכש 4500000520?
```
**What you'll get**: Total order value, breakdown by item, currency information.

### 4. Check Inventory Status
```
מה מצב המלאי של המוצר MZ-RM-C990-01?
```
**What you'll get**: Current stock levels, open orders, availability status.

### 5. Supplier Information
```
מי הספק של הזמנה 4500000520?
```
**What you'll get**: Supplier name, code, contact information, performance history.

### 6. Product Details
```
תן לי פרטים על גלגלי BKC-990
```
**What you'll get**: Product specifications, pricing, inventory levels, usage history.

### 7. Check Order Status
```
מה הסטטוס של הזמנת רכש 4500000520?
```
**What you'll get**: Order status, creation date, delivery dates, completion status.

### 8. Price Analysis
```
מה המחיר ליחידה של כל פריט בהזמנה 4500000520?
```
**What you'll get**: Detailed pricing for each item, price comparisons, cost analysis.

### 9. Reorder Recommendations
```
אילו פריטים צריך להזמין מחדש?
```
**What you'll get**: List of items below reorder point, recommended quantities, priority items.

### 10. Monthly Summary
```
תן לי סיכום של הזמנות החודש
```
**What you'll get**: Order count, total spending, top suppliers, category breakdown.

---

## 💡 Sample Conversations

### Conversation 1: Basic Information Retrieval
```
👤 User: מה המידע על הזמנת רכש 4500000520?

🤖 Agent: תודה על השאלה. הנה המידע המלא על הזמנת רכש 4500000520:

1. פרטי הזמנה:
   - מספר: 4500000520
   - תאריך: 21 באוקטובר 2019
   - ספק: USSU-VSF08
   - מטבע: USD

2. פריטים (7 פריטים):
   - שלדת BKC-990: 362 יחידות ב-$335.24
   - כידון: 362 יחידות ב-$11.56
   - מושב: 362 יחידות ב-$11.56
   - גלגלים: 724 יחידות ב-$14.45
   - מזלגות: 362 יחידות ב-$46.24
   - בלמים: 362 יחידות ב-$28.90
   - מערכת הנעה: 362 יחידות ב-$115.60

3. סיכום:
   - סך הכל: 2,896 יחידות
   - ערך כולל: $209,236.00
   - ניתן לסגירה: כן

👤 User: איזה פריט הכי יקר?

🤖 Agent: הפריט היקר ביותר הוא שלדת BKC-990 (MZ-RM-C990-01)
במחיר של $335.24 ליחידה, עם ערך כולל של $121,356.88 (362 יחידות).
זה מהווה כ-58% מערך ההזמנה הכולל.
```

### Conversation 2: Inventory Management
```
👤 User: האם יש מספיק מלאי לייצר 100 אופני BKC-990?

🤖 Agent: אבדוק את המלאי הנוכחי של כל הרכיבים...

בהתבסס על מבנה המוצר:
- שלדות: נדרש 100, במלאי: [checking...]
- כידונים: נדרש 100, במלאי: [checking...]
- מושבים: נדרש 100, במלאי: [checking...]
- גלגלים: נדרש 200, במלאי: [checking...]
...

👤 User: מה לעשות עם החלקים החסרים?

🤖 Agent: יש לי כמה המלצות:
1. הזמן באופן דחוף את [רשימת חלקים]
2. הספק המומלץ: USSU-VSF08
3. זמן אספקה משוער: X ימים
4. עלות משוערת: $X
```

---

## 🎯 Common Use Cases

### Procurement
- ✅ Review purchase orders
- ✅ Track spending
- ✅ Evaluate suppliers
- ✅ Analyze pricing trends

### Production
- ✅ Check material availability
- ✅ Plan production runs
- ✅ Identify bottlenecks
- ✅ Forecast requirements

### Inventory
- ✅ Monitor stock levels
- ✅ Identify reorder points
- ✅ Optimize stock levels
- ✅ Track slow-moving items

### Finance
- ✅ Track procurement budget
- ✅ Analyze costs
- ✅ Forecast spending
- ✅ Identify savings opportunities

---

## 📊 Response Quality

The agent provides:

### ✅ Accurate Data
- Real-time SAP OData API integration
- Complete purchase order details
- Up-to-date inventory levels

### ✅ Comprehensive Analysis
- (1) Current inventory details
- (2) Ordered quantities
- (3) Relevant dates
- (4) Recommendations based on status

### ✅ Hebrew Language Support
- Native Hebrew responses
- Technical terminology in Hebrew
- Natural language understanding

### ✅ Business Intelligence
- Trend analysis
- Cost optimization recommendations
- Risk identification
- Actionable insights

---

## 🔧 Integration Options

### Python API
```python
from utils.agent import invoke_agent

# Basic invocation
result = invoke_agent(
    agent_arn='arn:aws:bedrock-agentcore:...',
    prompt='מה המידע על הזמנה 4500000520?'
)

print(result['response'])
```

### CLI
```bash
python utils/agent.py invoke \
  'arn:aws:bedrock-agentcore:...' \
  'מה המידע על הזמנה 4500000520?'
```

### REST API
```bash
curl -X POST https://your-api-endpoint/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "מה המידע על הזמנה 4500000520?"
  }'
```

---

## 📚 Next Steps

### Learn More
- [📖 Full Example Questions](EXAMPLE_QUESTIONS.md) - Comprehensive list of questions by category
- [🎯 Use Cases](USE_CASES.md) - Real-world scenarios and role-based examples
- [🏗️ Architecture](ARCHITECTURE.md) - Technical architecture and integration details

### Advanced Features
- [🧪 Evaluation Framework](EVALUATION_METRICS.md) - How responses are evaluated
- [🚀 Deployment Guide](DEPLOYMENT_STATUS.md) - Deploy your own instance
- [🔐 Security](../README.md#security) - OAuth and authentication details

### Get Help
- Run tests: `python utils/test_e2e_agent.py`
- Check logs: `aws logs tail /aws/bedrock-agentcore/runtimes/...`
- Report issues: [GitHub Issues](https://github.com/roy2392/agentcore-langfuse-sap-agent/issues)

---

## 🎓 Training Resources

### Video Tutorials (Coming Soon)
- Getting Started (5 min)
- Common Questions (10 min)
- Advanced Features (15 min)

### Interactive Demos
- Live agent testing
- Sample conversation flows
- Response analysis

---

## ✨ Pro Tips

1. **Be Specific**: Include PO numbers or product codes for best results
2. **Ask Follow-ups**: The agent maintains context across the conversation
3. **Request Analysis**: Ask "why" and "what should I do" for recommendations
4. **Use Natural Language**: Both Hebrew and English work well
5. **Check Multiple Orders**: Compare orders to identify trends

---

## 🆘 Troubleshooting

### Common Issues

**Q: Agent not responding?**
A: Check that the agent is deployed: `python utils/test_e2e_agent.py`

**Q: Getting empty responses?**
A: Verify SAP connectivity and OAuth credentials

**Q: Responses in wrong language?**
A: System prompt is configured for Hebrew - check configuration

**Q: Tool not being called?**
A: Ensure tool name matches: `sap-get-po-target___get_complete_po_data`

---

**Quick Links**:
- [Agent Dashboard](https://console.aws.amazon.com/bedrock-agentcore)
- [Langfuse Traces](https://cloud.langfuse.com)
- [GitHub Repository](https://github.com/roy2392/agentcore-langfuse-sap-agent)

**Version**: 1.0 | **Last Updated**: November 2025
