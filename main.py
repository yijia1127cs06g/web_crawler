import argparse
import re
import getpass
from io import BytesIO
from bs4 import BeautifulSoup as bs
import requests
from PIL import Image
from PIL import ImageEnhance
import pytesseract
from prettytable import PrettyTable



PORTAL_URL = 'https://portal.nctu.edu.tw'
COURSE_URL = 'https://course.nctu.edu.tw'

headers = {
            'Host':'portal.nctu.edu.tw',
            'Referer': PORTAL_URL,
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13) AppleWebKit/604.1.38 (KHTML, like Gecko) Version/11.0 Safari/604.1.38',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Connection': 'keep-alive',
            'Accept-Language': 'zh-tw',
            'Accept-Encoding': 'br, gzip, deflate'
            }

def Startup():
    ''' 
        Check username and password
        Prepare login information 
        Return login info dictionary
    '''
    parser = argparse.ArgumentParser(description="Web crawler for NCTU class schedule")
    parser.add_argument('username', help="username of NCTU portal")
    args = parser.parse_args()
    username = args.username
    print(" Username: " + username)
    password = getpass.getpass(" Portal Password: ")
    data = {
        'username': args.username,
        'Submit2': '登入(Login)',
        'pwdtype': 'static',
        'password': password,
        'seccode': '0000'}
    return data

def checkLoginStatus(loginPage):
    loginPage.encoding = 'utf-8'
    content = bs(loginPage.text, 'html.parser')
    string = content.text
    string = re.sub(r'\n','',string)
    string = re.sub(r'\t','', string)
    string = re.sub(r'\r','', string)
    string = re.sub(r'\ufeff', '', string)
    loginStatus = re.split('[()]', string)    
    if "驗證碼錯誤" in loginStatus[1]:
        return 1
    if "請確認密碼是否正確" in loginStatus[1]:
        print("Wrong password")
        print("Please check your password and enter again")
        return 2
    return 0

def verifyCaptcha(image):
    def adjustBrightness(image, value):
        enhancer = ImageEnhance.Brightness(image)
        return enhancer.enhance(value)

    def adjustContrast(image, value):
        enhancer = ImageEnhance.Contrast(image)
        return enhancer.enhance(value)

    def identifier(image, brightValue, contrastValue):
        adjust = adjustBrightness(image, brightValue)
        adjust = adjustContrast(adjust, contrastValue)
        return pytesseract.image_to_string(adjust,config='--psm 7 -c tessedit_char_whitelist=0123456789')

    def testValidity(number):
        if len(number) == 4 and number.isdigit():
            return True
        else:
            return False

    numberList = dict()
    for i in range(15,18):
        bvalue = i/10;
        for j in range(20,90,10):
            cvalue = j/10
            number = identifier(image, bvalue, cvalue)
            if testValidity(number):
                return number
    return -1

def stripper(line):
    string = re.sub(r'\t', '', line)
    string = re.sub(r'\n', '', string)
    string = re.sub(r'\r', '', string)
    string = re.sub(r' ', '', string)
    return string

def Main():
    userData = Startup()

    while True:

        with requests.Session() as session:

            # Get cookie from page
            # session.headers.update(headers)
            loginPage = session.get(PORTAL_URL+'/portal/login.php', headers = headers)
            
            # Get Captcha image
            captchaPage = session.get(PORTAL_URL+'/captcha/pic.php', headers = headers)
            captchaImg = Image.open(BytesIO(captchaPage.content))
            captchaCode = verifyCaptcha(captchaImg)
            if captchaCode == -1:
                continue

            userData['seccode'] = captchaCode
            
            # Get Login cookie
            chkpasPage = session.post(PORTAL_URL+'/portal/chkpas.php?', 
                    headers = headers, data = userData)
            
            status = checkLoginStatus(chkpasPage)
            if status == 1:
                continue
            if status == 2:
                print(" Username: "+userData['username'])
                userData['password'] = getpass.getpass("Portal Password: ")
                continue

            
            # Get jwt secret infomation from portal relay system
            relayPage = session.get(PORTAL_URL+'/portal/relay.php?D=cos')
            
            # Prepare jwt data for course system verification
            relayPage.encoding = 'utf-8'
            soup = bs(relayPage.text, 'html.parser')
            
            payload={}
            for item in soup.find_all('input'):
                payload[item.get('id')]=item.get('value')
            payload['Chk_SSO'] = 'on'
           
            # Get the jwt cookie
            jwtPage = session.post(COURSE_URL+'/jwt.asp', data=payload)
            

            table = session.get(COURSE_URL+'/adSchedule.asp')
            if table.status_code == 302:
                print(" Fail to get the table")
                break
            
            # Parse the timetable to each row
            table.encoding = 'big5'
            soup = bs(table.text, 'html.parser')
            timetable = bs(str(soup.find_all('table')[1]), 'html.parser')

            
            mainRow = []          
            for element in timetable.find_all('td','dayOfWeek'):
                mainRow.append(element.font.string)

            ROWS = []
            rows = []
            i=0
            for line in timetable.find_all('td',['liststyle1', 'liststyle2']):
                rawdata = bs(str(line), 'html.parser')
                rows.append(stripper(rawdata.text).strip('\n'))
                i += 1
                if i == 9:
                    ROWS.append(rows)
                    i = 0
                    rows = []
            
            # Add each rows to prettytable
            x = PrettyTable()
            x.field_names = mainRow
            for rowline in ROWS:
                x.add_row(rowline)
            print(x)    
            break

if __name__ == '__main__':
    Main()
    
