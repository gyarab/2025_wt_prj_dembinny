# Parent FAQ — Class Fund Manager

Answers to common questions from parents about the Class Fund Manager.
If you cannot find the answer here, contact your child's class treasurer or teacher.

---

## 1. What is a Variable Symbol (VS) and why does my child have one?

A **Variable Symbol** is a numeric payment reference unique to your child — a string
of digits assigned by the system (its length can vary depending on how the class
account is set up).
Czech banks use it like a reference number — it tells the school fund treasurer
exactly whose payment has arrived.

Your child's VS is automatically assigned when they are registered in the system.
You will find it pre-filled when you scan a SPAYD QR code (see question 2).

**Example:** in many classes, if the class prefix is `04` and your child is the
third student registered, their VS is `04003`. In other classes, you may see a
different number of digits, but the VS shown on the payment request is always the
correct one to use.

You should include this number in the VS field every time you make a bank transfer
to the class fund account — even when a QR code is not available.

---

## 2. What is a SPAYD QR Code and how do I use it?

**SPAYD** stands for *Short Payment Descriptor*. It is the Czech and Slovak banking
standard for encoding payment details in a QR code.

When you scan the QR code on a payment request with your **mobile banking app**:

1. Open your bank's mobile app.
2. Choose **Scan QR** or **Pay by QR** (exact wording differs per bank).
3. Point the camera at the QR code shown on the payment page.
4. The app will automatically fill in:
   - The class bank **account number** (IBAN)
   - The **amount** requested
   - Your child's **Variable Symbol**
5. Review the pre-filled details, then confirm the payment as normal.

No typing required — the QR eliminates the chance of entering the wrong
account number or symbol.

---

## 3. How do I pay if I do not have a smartphone or mobile banking?

Make a standard **bank transfer** to the class fund account:

1. Ask the class treasurer for the **account number** and **IBAN**.
2. Enter the amount specified in the payment request.
3. Enter your child's **Variable Symbol** in the VS field.
4. Leave the message field blank (or write your child's name — this is optional).

The treasurer will manually confirm the transaction once they see it in the
bank statement.

---

## 4. I paid but the app still shows me as owing money. What should I do?

Bank transfers are **not yet imported automatically** in the current version.
The treasurer must manually confirm each payment.

Steps to resolve:

1. **Wait 1–2 school days** — the treasurer may not have reviewed payments yet.
2. If it still shows as unpaid, **contact the class treasurer** and tell them:
   - The date you paid
   - The exact amount
   - Your child's Variable Symbol
3. The treasurer will find the transfer in the bank statement and confirm it
   in the system.

---

## 5. Can I see my child's full payment history?

Yes. Log in at the app URL and you will see:

- All **payment requests** assigned to your child
- Which requests are **paid**, **pending**, or **unpaid**
- Each individual **transaction** with its date and amount
- The total amount **paid** and the total currently **owed**

You can only see your own child's data — other parents' financial information
is never visible to you.

---

## 6. What if I overpay or underpay?

- **Overpayment:** The extra amount stays in the class fund as a credit
  for future requests. Contact the treasurer if you need it refunded.
- **Underpayment (partial payment):** A transaction is recorded for the
  amount actually received. The outstanding balance continues to appear
  in your payment requests until the full amount is settled.

---

## 7. My child changed class or left the school. What happens to their data?

Contact the class treasurer or teacher to update your child's status.
A treasurer can **deactivate** a student profile, which removes the student
from future payment requests.
Historical transaction records are kept for accounting purposes but the
student stops receiving new payment assignments.

---

## 8. What data does the app store about me and my child?

The app stores only what is necessary to manage the class fund:

| Data | Why it is stored |
|---|---|
| Name and surname | Displayed in the treasurer dashboard and notifications |
| Email address | Login credential and notification emails |
| Username | Login credential |
| Variable Symbol | Matching bank transfers to the correct student |
| Payment records | Audit trail — who paid, how much, when |
| Parent–child link | So parents can see their child's payment status |

No payment card numbers, bank credentials, or sensitive financial data
beyond the above are stored by this application.

---

## 9. How is my data secured?

- **Passwords** are cryptographically hashed using Django's default PBKDF2-SHA256
  algorithm before they are stored in the login database. In limited
  administrative workflows (such as bulk account imports), an initial
  password may be handled in plain text for account creation, but it is not
  retained longer than necessary for that process.
- **Database connections** between the app and Supabase PostgreSQL use TLS
  encryption in transit.
- **Access control** is enforced at every page: you can only see your own
  child's data. Other parents, students from other classes, and unrelated
  users cannot access your records.
- The application is hosted on **Render.com**, a reputable cloud platform
  with server-side security and automated certificate management.
- This application is developed as a school project and is **not a financial
  institution**. It does not touch your bank account directly — it only
  records whether payments have been confirmed by the treasurer.

---

## 10. Who do I contact if something is wrong?

| Issue | Contact |
|---|---|
| Wrong amount shown, transaction not confirmed | Class treasurer |
| Login problems, forgotten password | Class treasurer or teacher |
| Data privacy request (GDPR) | Class teacher → school administration |
| Technical bug in the application | Open a GitHub issue at `github.com/gyarab/2025_wt_prj_dembinny` |

