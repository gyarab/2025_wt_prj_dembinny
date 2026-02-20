# Class Fund Manager - Dominik Dembinný

## Overview

**Class Fund Manager** is a Django-based web application designed to streamline the collection, tracking, and management of class funds. Built as a school project, this system replaces manual tracking by providing a centralized platform where students can view their financial obligations, and the class treasurer (administrator) can manage the budget with full transparency.

## Key Features

### For Students (Standard Users)

* **User Accounts:** Secure login for every student in the class.
* **Payment Dashboard:** A personalized view showing pending payment requests (e.g., field trips, class events, supplies) and a history of completed payments.
* **Payment Methods Info:** Quick access to the class bank account details and QR codes for easy, error-free bank transfers.

### For the Administrator (Class Treasurer)

* **Bank Synchronization:** Dedicated admin tools to record incoming bank transfers and link them to specific student accounts and payment requests.
* **Request Generation:** The ability to create new payment requests and assign them to the entire class or specific students.
* **Budget Overview:** An automated calculator displaying the current total amount in the class fund.
* **Expense Tracking:** Options to log and publish class budget spendings so all users can see how the collected money is being used.

## Tech Stack

* **Backend:** Python, Django
* **Database:** SQLite / PostgreSQL (configured via Django ORM)
* **Frontend:** HTML, CSS, Django Templates

## Project Goals

* Automate the tracking of class money to reduce errors.
* Provide financial transparency to all classmates regarding collections and expenditures.
* Demonstrate backend web development skills using the Django framework and relational databases.
