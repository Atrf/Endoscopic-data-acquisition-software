import sys
from PyQt5 import QtWidgets, QtGui, QtCore
import sqlite3
import cv2
import os
import numpy as np
import time, datetime
from frame2dicom import encode_to_dicom
import random
import uuid
from pydicom import dcmread, uid
from pynetdicom import AE
import warnings
warnings.filterwarnings("ignore")
class EditDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(EditDialog, self).__init__(parent)
        self.setWindowTitle("编辑用户信息")
        self.setStyleSheet("background-color: white; color: black;")


        # 创建姓名输入框
        self.name_label = QtWidgets.QLabel("Name: ")
        self.name_edit = QtWidgets.QLineEdit()

        # 创建年龄输入框
        self.age_label = QtWidgets.QLabel("Age:")
        self.age_edit = QtWidgets.QSpinBox()

        # 创建性别选择框
        self.gender_label = QtWidgets.QLabel("Gender:")
        self.gender_combo = QtWidgets.QComboBox()
        self.gender_combo.addItem("M")
        self.gender_combo.addItem("F")
        self.gender_combo.addItem("O")

        # 创建Physician输入框
        self.Physician_label = QtWidgets.QLabel("Physician:")
        self.Physician_edit = QtWidgets.QLineEdit()

        # 创建comment输入框
        self.comment_label = QtWidgets.QLabel("comment:")
        self.comment_edit = QtWidgets.QLineEdit()

        # 创建确认按钮
        self.confirm_button = QtWidgets.QPushButton("确认")
        self.confirm_button.clicked.connect(self.accept)

        # 创建取消按钮
        self.cancel_button = QtWidgets.QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)

        # 创建表单布局
        self.form_layout = QtWidgets.QFormLayout()
        self.form_layout.addRow(self.name_label, self.name_edit)
        self.form_layout.addRow(self.age_label, self.age_edit)
        self.form_layout.addRow(self.gender_label, self.gender_combo)
        self.form_layout.addRow(self.Physician_label, self.Physician_edit)
        self.form_layout.addRow(self.comment_label, self.comment_edit)

        # 创建按钮布局
        self.button_layout = QtWidgets.QHBoxLayout()
        self.button_layout.addWidget(self.confirm_button)
        self.button_layout.addWidget(self.cancel_button)

        # 创建主布局
        self.main_layout = QtWidgets.QVBoxLayout()
        self.main_layout.addLayout(self.form_layout)
        self.main_layout.addLayout(self.button_layout)

        self.setLayout(self.main_layout)


def updatedatabase(info, database_path):
    conn = sqlite3.connect(database_path)
    c = conn.cursor()
    current_date = datetime.date.today()
    current_time = datetime.datetime.now()
    # 插入患者信息
    c.execute("SELECT * FROM PatientLevel WHERE PatID = ?", (info['Patient']['PatID'],))
    if c.fetchone() is None:  # 如果患者（Patient）不存在于数据库
        c.execute("""
                INSERT INTO PatientLevel(PatID, PatNam, PatBirDate, PatSex, InsertDate, InsertTime)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (info['Patient']['PatID'], info['Patient']['PatNam'],
                  info['Patient']['PatBirDate'], info['Patient']['PatSex'],
                  current_date, current_time
                  )
            )
    # 检查并插入检查信息
    c.execute("SELECT * FROM StudyLevel WHERE StuInsUID = ?", (info['Study']['StuInsUID'],))
    if c.fetchone() is None:  # 如果检查(Study)不存在于数据库
        c.execute("""
            INSERT INTO StudyLevel(StuInsUID, StuID, StuDate, StuTime, AccNum, PatAge, PatSize, PatWeight, PatID, InsertDate, InsertTime)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (info['Study']['StuInsUID'], info['Study']['StuID'],
                  info['Study']['StuDate'], info['Study']['StuTime'],
                  info['Study']['AccNum'], info['Study']['PatAge'],
                  info['Study']['PatSize'], info['Study']['PatWeight'],
                  info['Patient']['PatID'],
                  current_date, current_time)
                )

        # 检查并插入序列信息
        c.execute("SELECT * FROM SeriesLevel WHERE SerInsUID = ?", (info['Series']['SerInsUID'],))
        if c.fetchone() is None:  # 如果序列（Series）不存在于数据库
            c.execute("""
                INSERT INTO SeriesLevel(SerInsUID, SerNum, Modality, ProNam, SerDes, BodParExa, StuInsUID, InsertDate, InsertTime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (info['Series']['SerInsUID'], info['Series']['SerNum'],
                  info['Series']['Modality'], info['Series']['ProNam'],
                  info['Series']['SerDes'], info['Series']['BodParExa'],
                  info['Study']['StuInsUID'],
                  current_date, current_time)
                )

        # 检查并插入图像信息
        c.execute("SELECT * FROM ImageLevel WHERE SOPInstanceUID = ?", (info['Image']['SOPInstanceUID'],))
        if c.fetchone() is None:  # 如果图像（Image）不存在于数据库
            c.execute("""
                INSERT INTO ImageLevel(SOPInstanceUID, ImaNum, SOPClaUID, TransferSyntax, StoragePath, SerInsUID, InsertDate, InsertTime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (info['Image']['SOPInstanceUID'], info['Image']['ImaNum'],
                  info['Image']['SOPClaUID'], info['Image']['TransferSyntax'],
                  info['Image']['StoragePath'], info['Series']['SerInsUID'],
                  current_date, current_time)
                )

        # 提交数据库更改
        conn.commit()
        # 关闭数据库连接
        conn.close()

def age_to_birthdate(age):
    current_date = datetime.datetime.now()

    # 计算出生日期
    birthdate = current_date - datetime.timedelta(days=365 * int(age))

    return birthdate

def add_send_flag_column(database_file):
    # 连接到数据库
    conn = sqlite3.connect(database_file)
    cursor = conn.cursor()

    # 检查sendFlag字段是否已存在
    cursor.execute("PRAGMA table_info(imageLevel)")
    columns = cursor.fetchall()
    if any('sendFlag' in col for col in columns):
        conn.close()
        return

    # 执行ALTER TABLE语句
    alter_query = "ALTER TABLE imageLevel ADD COLUMN sendFlag INT DEFAULT 0;"
    cursor.execute(alter_query)

    # 提交更改并关闭连接
    conn.commit()
    conn.close()
    print("sendFlag字段已成功添加。")

def generateUniqueID(prefix, type):
    if type == "PatID":
        # Use a shorter UUID for Patient ID
        return f"{prefix}_P{str(uuid.uuid4())[:8]}"
    elif type == "StudyInsUID":
        # Generate Study Instance UID
        return f"2.25.{prefix}.{uuid.uuid4()}"
    elif type == "SerInsUID":
        # Generate Series Instance UID
        return f"3.25.{prefix}.{uuid.uuid4()}"
    else:
        raise ValueError("Invalid type")


def dicom_send_image(file_name, own_ae_title, peer_ae_title, peer_ip, peer_port):
    # Create an Application Entity with the specified AE title

    ae = AE(ae_title=own_ae_title)

    # Read the DICOM file to determine its SOP Class UID
    ds = dcmread(file_name, force=True)
    ds.SOPClassUID = uid.SecondaryCaptureImageStorage
    # Add a requested presentation context based on the SOP Class UID
    # sop_class = ds.SOPClassUID
    sop_class = uid.SecondaryCaptureImageStorage
    ae.add_requested_context(sop_class)
    # ae.add_requested_context(CTImageStorage)

    # Associate with the peer AE at the specified IP and port using the specified AE title
    assoc = ae.associate(peer_ip, peer_port, ae_title=peer_ae_title)

    if assoc.is_established:
        # Send the DICOM dataset using the C-STORE service
        status = assoc.send_c_store(ds)

        print("reading")
        # Check the status of the storage request
        if status:
            print('C-STORE request status: 0x{0:04x}'.format(status.Status))
        else:
            print('Connection timed out, was aborted or received invalid response')

        # Release the association
        assoc.release()
        return True
    else:
        print('Association rejected, aborted or never connected')
        return False

def send_images_to_target_system(sqlite_db_filename, own_ae_title, peer_ae_title, peer_ip, peer_port):
    """
    将 sendFlag = 0 的图像发送到目标系统

    :param sqlite_db_filename: SQLite 数据库文件名
    :param own_ae_title, peer_ae_title, peer_ip, peer_port: 图像发送相关参数，自身AE Title, 发送目标 AE Title， 发送目标 IP， 发送目标端口号
    """
    try:
        # 连接到数据库

        conn = sqlite3.connect(sqlite_db_filename)
        conn.row_factory = sqlite3.Row  # 设置行工厂
        cursor = conn.cursor()

        # 检索 sendFlag = 0 的图像记录
        cursor.execute("SELECT * FROM imageLevel WHERE sendFlag = 0 or sendFlag is Null")
        unsend_image_records = cursor.fetchall()
        # print(unsend_image_records)
        # 遍历并发送图像
        for image_record in unsend_image_records:
            storage_path = image_record['StoragePath']
            sop_ins_uid = image_record['SOPInstanceUID']
            print(storage_path, sop_ins_uid)
            # 发送图像
            if dicom_send_image(storage_path, own_ae_title, peer_ae_title, peer_ip, peer_port):
                # 更新数据库中的 sendFlag

                strSQL = "UPDATE imageLevel SET sendFlag = 1 WHERE SOPInstanceUID = '" + sop_ins_uid + "'"
                # print("准备发送图像：", strSQL)
                cursor.execute(strSQL)
                print("成功发送图像：", sop_ins_uid)

        # 提交数据库更改
        conn.commit()

    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        return
    except Exception as e:
        # 打印异常信息
        print(f"An error occurred: {e}")
    finally:
        # 关闭数据库连接
        print("系统退出")
        if conn:
            conn.close()
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        # 设置窗口标题
        self.setWindowTitle("用户界面")

        # 设置窗口大小
        self.resize(1000, 800)

        # 设置窗口背景色为黑色
        self.setStyleSheet("background-color: black;")

        # 创建姓名和性别部件
        self.name_label = QtWidgets.QLabel(self)
        self.name_label.setStyleSheet("color: white; font: bold 25px;")  # 设置字体样式和大小
        self.name_label.setGeometry(QtCore.QRect(100, 100, 200, 120))  # 改变部件位置
        self.name_label.setText("Name: ")
        self.name_label.mousePressEvent = self.show_dialog

        self.gender_label = QtWidgets.QLabel(self)
        self.gender_label.setStyleSheet("color: white; font: bold 25px;")  # 设置字体样式和大小
        self.gender_label.setGeometry(QtCore.QRect(100, 215, 200, 40))  # 改变部件位置
        self.gender_label.setText("gender: ")
        # self.gender_label.mousePressEvent = self.show_dialog

        self.age_label = QtWidgets.QLabel(self)
        self.age_label.setStyleSheet("color: white; font: bold 25px;")  # 设置字体样式和大小
        self.age_label.setGeometry(QtCore.QRect(100, 255, 200, 40))  # 改变部件位置
        self.age_label.setText("age: ")

        # 创建日期和时间部件
        self.datetime_label = QtWidgets.QLabel(self)
        self.datetime_label.setStyleSheet("color: white; font: bold 25px;")
        self.datetime_label.setGeometry(QtCore.QRect(100, 360, 400, 80))

        # Physician & Comment
        self.ph_label = QtWidgets.QLabel(self)
        self.ph_label.setStyleSheet("color: white; font: bold 25px;")  # 设置字体样式和大小
        self.ph_label.setGeometry(QtCore.QRect(100, 560, 400, 40))  # 改变部件位置
        self.ph_label.setText("Physician: ")

        self.com_label = QtWidgets.QLabel(self)
        self.com_label.setStyleSheet("color: white; font: bold 25px;")  # 设置字体样式和大小
        self.com_label.setGeometry(QtCore.QRect(100, 600, 400, 40))  # 改变部件位置
        self.com_label.setText("Comment: ")

        # 创建图像区域
        self.lbl_Image = QtWidgets.QLabel(self)
        self.lbl_Image.setGeometry(QtCore.QRect(600, 200, 720, 720))
        self.lbl_Image.setStyleSheet("background-color: white;")
        self.lbl_Image.mousePressEvent = self.save_snapshot

        # 打开摄像头
        self.cap = cv2.VideoCapture(0)

        # 设置摄像头分辨率为 1280x720
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        # 创建定时器，每隔 50 毫秒（约30帧）触发一次更新图像
        self.image_timer = QtCore.QTimer(self)
        self.image_timer.timeout.connect(self.update_image)
        self.image_timer.start(50)

        # 创建定时器，每秒更新日期和时间
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_datetime)
        self.timer.start(1000)  # 每隔1秒触发一次

        # 截图
        # self.snapshot_button = QPushButton('截图', self)
        # self.snapshot_button.setStyleSheet("background-color : white")
        # self.snapshot_button.setGeometry(QtCore.QRect(100, 800, 75, 24))
        # self.snapshot_button.clicked.connect(self.save_snapshot)


        # Dicom information
        self.ImaNum = 0
        self.info = {}

    def update_info(self, name, gender, age, physician, comment):

        self.info.setdefault("Patient", {})["PatNam"] = name
        self.info.setdefault("Patient", {})["PatBirDate"] = age_to_birthdate(age)
        self.info.setdefault("Patient", {})["PatSex"] = gender
        self.info.setdefault("Patient", {})["NumPatRelStu"] = 0
        self.info.setdefault("Patient", {})["NumPatRelSer"] = 0
        self.info.setdefault("Patient", {})["NumPatRelIma"] = 0

        self.info.setdefault("Study", {})["StuID"] = 1
        self.info.setdefault("Study", {})["StuDate"] = datetime.datetime.now().strftime('%Y-%m-%d')
        self.info.setdefault("Study", {})["StuTime"] = datetime.datetime.now().strftime('%H:%M:%S')
        self.info.setdefault("Study", {})["AccNum"] = 1
        self.info.setdefault("Study", {})["PatAge"] = age
        self.info.setdefault("Study", {})["PatSize"] = 170
        self.info.setdefault("Study", {})["PatWeight"] = 70
        self.info.setdefault("Study", {})["NumStuRelSer"] = 0
        self.info.setdefault("Study", {})["NumStuRelIma"] = 0

        self.info.setdefault("Series", {})["SerNum"] = 1
        self.info.setdefault("Series", {})["Modality"] = "ES"
        self.info.setdefault("Series", {})["ProNam"] = physician
        self.info.setdefault("Series", {})["SerDes"] = comment
        self.info.setdefault("Series", {})["BodParExa"] = "stomach"
        self.info.setdefault("Series", {})["NumSerRelIma"] = 0

        self.info.setdefault("Patient", {})["PatID"] = generateUniqueID('Pat', "PatID")
        self.info.setdefault("Study", {})["StuInsUID"] = generateUniqueID("Stu", "StudyInsUID")
        self.info.setdefault("Series", {})["SerInsUID"] = generateUniqueID("Ser", "SerInsUID")

    def show_dialog(self, event):
        # 创建编辑对话框
        dialog = EditDialog(self)

        # 获取当前患者姓名和性别
        current_name = self.name_label.text()
        current_gender = self.gender_label.text()

        # 设置对话框中的初始值
        dialog.name_edit.setText(current_name)

        # 设置年龄输入范围
        dialog.age_edit.setRange(0, 150)

        # 设置对话框中的初始值
        if current_gender == "男":
            dialog.gender_combo.setCurrentIndex(0)
        elif current_gender == "女":
            dialog.gender_combo.setCurrentIndex(1)

        # 显示对话框，并等待用户操作
        if dialog.exec_() == QtWidgets.QDialog.Accepted:

            # 获取用户输入的值
            new_name = dialog.name_edit.text()
            new_age = dialog.age_edit.value()
            new_gender = dialog.gender_combo.currentText()
            physician = dialog.Physician_edit.text()
            comment = dialog.comment_edit.text()


            # 更新患者姓名和性别栏目
            self.name_label.setText("Name: " + new_name)
            self.gender_label.setText("gender: " + new_gender)
            self.age_label.setText("age: " + str(new_age))
            self.ph_label.setText("Physician: "+physician)
            self.com_label.setText("Comment: "+comment)
            self.update_info(new_name, new_gender, new_age, physician, comment)

    def update_datetime(self):
        # 更新日期和时间
        current_datetime = QtCore.QDateTime.currentDateTime().toString("yyyy-MM-dd \n hh:mm:ss")
        self.datetime_label.setText(current_datetime)

    def apply_mask(self, image, mask_center, mask_radius):
        mask = np.zeros_like(image)
        height, width, _ = image.shape
        cv2.circle(mask, mask_center, mask_radius, (255, 255, 255), -1)

        masked_image = cv2.bitwise_and(image, mask)
        return masked_image

    def crop_center(self, image, crop_width, crop_height):
        height, width = image.shape[:2]
        start_x = (width - crop_width) // 2
        start_y = (height - crop_height) // 2
        end_x = start_x + crop_width
        end_y = start_y + crop_height
        cropped_image = image[start_y:end_y, start_x:end_x]
        return cropped_image

    def update_image(self):
        # 读取摄像头图像
        ret, frame = self.cap.read()
        # 如果成功读取图像
        # 调整图像大小为 720x720
        # frame = cv2.resize(frame, (720, 720))
        frame = self.crop_center(frame, 720, 720)

        # 创建一个圆形遮罩
        mask_center = (frame.shape[1] // 2, frame.shape[0] // 2)  # 图像中心点
        mask_radius = min(frame.shape[1] // 2, frame.shape[0] // 2)  # 遮罩半径

        # 应用遮罩
        m_frame = self.apply_mask(frame, mask_center, mask_radius)
        # frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        # 将图像转换为 Qt 图像格式
        qimage = QtGui.QImage(m_frame.data, m_frame.shape[1], m_frame.shape[0], QtGui.QImage.Format_RGB888).rgbSwapped()
            # 将图像显示在 lbl_Image 上
        pixmap = QtGui.QPixmap.fromImage(qimage)
        self.lbl_Image.setPixmap(pixmap)

    def closeEvent(self, event):
        # 释放摄像头资源
        self.cap.release()
        event.accept()


    def save_snapshot(self, event):
        # 读取摄像头图像
        ret, frame = self.cap.read()

        frame = self.crop_center(frame, 720, 720)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        p_id = random.randint(1, 1000000)
        p_sex = self.gender_label.text()[-2:]
        p_age = int(self.age_label.text().split(': ')[1])
        comments = self.com_label.text().split(': ')[1]
        physician = self.ph_label.text().split(': ')[1]
        self.ImaNum += 1

        if ret:
            if not os.path.exists('./ImageStoragePath'):
                os.mkdir('./ImageStoragePath')
            info = encode_to_dicom(frame, self.name_label.text(), id=p_id, sex=p_sex, age=p_age, ImaNum=self.ImaNum,
                            Comments=comments, Physician=physician)
            self.info.setdefault('Image', {})['SOPInstanceUID'] = info["SOPInsUID"]
            self.info.setdefault('Image', {})['SOPClaUID'] = info["SOPClaUID"]
            self.info.setdefault('Image', {})['ImaNum'] = self.ImaNum
            self.info.setdefault('Image', {})['StoragePath'] = info["StoragePath"]
            self.info.setdefault('Image', {})['TransferSyntax'] = info["TransferSyntax"]
            self.info.setdefault('Image', {})['sendFlag'] = 0

            updatedatabase(self.info, "./pcas2023.db")
            cv2.imwrite("./ImageStoragePath/"+time.strftime('%Y-%m-%d-%H-%M-%S')+".png", frame)

            send_images_to_target_system('.\pcas2023.db',
                                         'SC_Capture', 'RADIANT', '127.0.0.1', 11112)




if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())