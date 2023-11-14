import os
import re
import gc
import requests
from pypdf import PdfWriter, PdfReader
from multiprocessing.dummy import Pool
from reportlab.pdfgen import canvas
from PIL import Image
from utils.encrypt import createVerificationData
from utils.file import createFolder, deleteFolderAndFile


# 获取单页pdf信息,并返回接受到的内容
def getPagePdfInfo(url, ua):
    headers = {
        'User-Agent': ua,
        'Referer': 'https://www.cxstar.com/'
    }
    return requests.get(url, headers=headers, stream=True).content


def pdfDownload(book_data, book_id, ua):
    # 书名
    book_name = book_data["title"]
    # 移除不合法字符并替换为空格
    valid_characters = re.sub(r'[^\w.-]', ' ', book_name)
    # 去除多余的空格
    sanitized_filename = re.sub(r'\s+', ' ', valid_characters)
    # 去除两端空格
    book_name = sanitized_filename.strip()
    # 页数
    total_page = int(book_data["totalPage"])
    # 目录数据
    catalog = book_data["catalog"]
    # 链接地址
    file_path = book_data["filePath"]

    pdf_name = book_name + ".pdf"
    pdf_writer = PdfWriter()
    if not os.path.exists(book_id):
        createFolder(book_id)

    print("正在下载单页pdf中,请等待...")
    page_pdf_list = [(file_path + "&pageno=" + str(i) + "&bookruid=" + book_id + "&readtype=pdf",
                      book_id + "/" + str(i) + ".pdf", ua) for i in range(total_page)]
    pool = Pool()
    if not book_data.get("webPath"):
        pool.map(pagePdfDownload, page_pdf_list)
    else:
        pool.map(saveImagePdf, page_pdf_list)
    pool.close()
    pool.join()

    print("正在合并所有pdf中...")
    for i in range(total_page):
        temp_file_name = book_id + "/" + str(i) + ".pdf"
        with open(temp_file_name, 'rb+') as temp_pdf_file:
            pdf_reader = PdfReader(temp_pdf_file)
            total_pages = len(pdf_reader.pages)
            if i != total_page - 1 and total_pages != 1:
                total_pages = total_pages - 1
            for j in range(total_pages):
                pdf_writer.add_page(pdf_reader.pages[j])

    print("正在为书籍增加书签中...")
    add_bookmarks(pdf_writer, catalog)

    with open(pdf_name, "wb") as output_pdf:
        pdf_writer.write(output_pdf)

    pdf_writer.close()
    del pdf_writer
    gc.collect()

    # 删除缓存的文件及目录
    print("正在删除临时文件及目录...")
    deleteFolderAndFile(book_id)

    current_path = os.getcwd()
    print("下载完毕，书籍位置：" + current_path + "\\" + pdf_name)


# 下载单页pdf到指定位置
def pagePdfDownload(page_pdf):
    url = page_pdf[0]
    encrypt_data = createVerificationData()
    url = url + "&nonce=" + encrypt_data["nonce"] + "&stime=" + encrypt_data["stime"] + "&sign=" + encrypt_data["sign"]
    file_name = page_pdf[1]
    ua = page_pdf[2]

    if not os.path.exists(file_name):
        temp = getPagePdfInfo(url, ua)
        with open(file_name, 'wb') as temp_file:
            temp_file.write(temp)


# 将图片保存为pdf并下载
def saveImagePdf(page_pdf):
    verification = createVerificationData()
    url = f'{page_pdf[0]}&nonce={verification["nonce"]}&stime={verification["stime"]}&sign={verification["sign"]}'
    file_name = page_pdf[1]
    ua = page_pdf[2]
    temp_file_name = file_name.split(".")[0] + ".png"

    # 如果存在该pdf文件
    if os.path.exists(file_name):
        return

    # 如果不存在该png文件
    if not os.path.exists(temp_file_name):
        temp = getPagePdfInfo(url, ua)
        with open(temp_file_name, "wb") as f:
            f.write(temp)

    # 将图片转换为PDF
    image = Image.open(temp_file_name)
    image_width, image_height = image.size

    pdf_file_name = file_name
    pdf = canvas.Canvas(pdf_file_name, pagesize=(image_width, image_height))
    pdf.drawImage(temp_file_name, 0, 0, width=image_width, height=image_height)
    pdf.save()


# 增加书籍目录
def add_bookmarks(pdf_writer, bookmarks, parent=None):
    for bookmark_data in bookmarks:
        title = bookmark_data["title"]
        page = int(bookmark_data["page"]) - 1
        bookmark = pdf_writer.add_outline_item(title, page, parent=parent)
        children = bookmark_data.get("children", [])
        add_bookmarks(pdf_writer, children, parent=bookmark)
