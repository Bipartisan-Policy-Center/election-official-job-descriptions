import gspread

gc = gspread.service_account(filename='gspread_credentials.json')
sht1 = gc.open_by_key('1t-oMIQVFW1uPRjjQ0Ffnf7w65C-uF1HKFQNp0hFgyzg')
worksheet = sht1.get_worksheet(0)

worksheet.update([df.fillna("").columns.values.tolist()] + df.fillna("").values.tolist())