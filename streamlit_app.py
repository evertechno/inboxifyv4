import streamlit as st
from email_validator import validate_email, EmailNotValidError
import dns.resolver
import smtplib
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

# Function to check email validity
def validate_email_address(email, blacklist, custom_sender="test@example.com"):
    """Enhanced email validation with DNS, SMTP, and blacklist checks."""
    try:
        # Step 1: Syntax validation
        validate_email(email)
    except EmailNotValidError as e:
        return email, "Invalid", f"Invalid syntax: {str(e)}"
    
    domain = email.split("@")[-1]

    # Step 2: Blacklist check
    if domain in blacklist:
        return email, "Blacklisted", "Domain is blacklisted."

    # Step 3: DNS Validation
    try:
        mx_records = dns.resolver.resolve(domain, "MX")
    except dns.resolver.NXDOMAIN:
        return email, "Invalid", "Domain does not exist."
    except dns.resolver.Timeout:
        return email, "Invalid", "DNS query timed out."
    except Exception as e:
        return email, "Invalid", f"DNS error: {str(e)}"

    # Step 4: SMTP Validation
    try:
        mx_host = str(mx_records[0].exchange).rstrip(".")
        smtp = smtplib.SMTP(mx_host, timeout=10)
        smtp.helo()
        smtp.mail(custom_sender)
        code, _ = smtp.rcpt(email)
        smtp.quit()
        if code == 250:
            return email, "Valid", "Email exists and is reachable."
        elif code == 550:
            return email, "Invalid", "Mailbox does not exist."
        elif code == 451:
            return email, "Greylisted", "Temporary error, try again later."
        else:
            return email, "Invalid", f"SMTP response code {code}."
    except smtplib.SMTPConnectError:
        return email, "Invalid", "SMTP connection failed."
    except Exception as e:
        return email, "Invalid", f"SMTP error: {str(e)}"

    return email, "Invalid", "Unknown error."

# Streamlit App
st.title("Inboxify by EverTech")

# Additional Information
st.write("""
**For Inboxify Mobile App please visit [Amazon Appstore](https://www.amazon.com/gp/product/B0DV3S92JY)** 
""")

# Blacklist upload
blacklist_file = st.file_uploader("Upload a blacklist file (optional)", type=["txt"])
blacklist = set()
if blacklist_file:
    blacklist = set(line.strip() for line in blacklist_file.read().decode("utf-8").splitlines())
    st.write(f"Loaded {len(blacklist)} blacklisted domains.")

# File upload
uploaded_file = st.file_uploader("Upload a .txt file with emails", type=["txt"])
if uploaded_file:
    emails = uploaded_file.read().decode("utf-8").splitlines()

    st.write(f"Processing {len(emails)} emails...")

    # Process emails
    results = []
    progress = st.progress(0)

    with ThreadPoolExecutor(max_workers=50) as executor:  # Increase max workers to handle more emails
        futures = [executor.submit(validate_email_address, email.strip(), blacklist) for email in emails if email.strip()]
        for idx, future in enumerate(as_completed(futures)):
            results.append(future.result())
            progress.progress((idx + 1) / len(emails))

    # Display results
    df = pd.DataFrame(results, columns=["Email", "Status", "Message"])
    st.dataframe(df)

    # Summary report
    st.write("### Summary Report")
    st.write(f"Total Emails Processed: {len(emails)}")
    for status in ["Valid", "Invalid", "Greylisted", "Blacklisted"]:
        count = df[df["Status"] == status].shape[0]
        st.write(f"{status} Emails: {count}")

    # Export results
    csv = df.to_csv(index=False)
    st.download_button("Download Results", data=csv, file_name="email_validation_results.csv", mime="text/csv")
