import pydicom
import numpy as np
import datetime
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from base64 import b64encode, b64decode
from Crypto.Signature import pkcs1_15
from Crypto.Hash import MD5
from Crypto.PublicKey import RSA
from pydicom.dataset import FileDataset, FileMetaDataset, DataElement
from pydicom.sequence import Dataset, Sequence
from pydicom.uid import UID, generate_uid
import time
import hashlib

def generate_dicom_hash(ds, tags):
    # 哈希值生成器
    hash_generator = hashlib.sha256()

    # 遍历指定的标签列表
    for tag in tags:
        # 获取标签的值
        tag_value = ds.get(tag, None)

        # 将标签值转换为字节并更新哈希值生成器
        if tag_value is not None:
            tag_bytes = str(tag_value).encode('utf-8')
            hash_generator.update(tag_bytes)

    # 计算哈希值
    hash_value = hash_generator.hexdigest()

    return hash_value


def segment_and_embed_hashes(image_data, auth_item):
    # 读取图像数据
    h, w = image_data.shape
    n=2
    m=2
    dis_h=int(np.floor(h/n))
    dis_w=int(np.floor(w/m))
    num=0
    for i in range(n):
        for j in range(m):
            sub=image_data[dis_h*i:dis_h*(i+1),dis_w*j:dis_w*(j+1)]
            sub = sub.tobytes()
            hash_value = hashlib.md5(sub).hexdigest()
            auth_item.add_new([0x9001,0x0008+num], 'LT', hash_value)
            num += 1

    return auth_item

def entropy(in_ds, iamge_arr, tags):
    # 创建序列
    auth_sequence = Sequence()
    # 为序列创建第一组新项目
    auth_item1 = Dataset()
    ds = in_ds
    image_data = iamge_arr
    hash_val = hashlib.md5(image_data).hexdigest()
    message = image_data.tobytes()

    private_key = Ed25519PrivateKey.generate()
    signature = private_key.sign(message)  # 数字签名
    public_key = private_key.public_key()

    with open("private_key.pem", 'wb') as f:
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        f.write(pem)
    # 保存公钥到文件

    with open("public_key.pem", 'wb') as f:
        pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        f.write(pem)

    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw)  # 公钥

    s = ""
    for t in tags:
        s += t
        s += " "

    hash_value_tag = generate_dicom_hash(ds, tags)  # 属性哈希值
    # 添加数据到第一组项目
    auth_item1.add_new((0x9001, 0x0001), 'OB', signature)
    auth_item1.add_new((0x9001, 0x0002), 'DA', "20231124")  # 格式为
    auth_item1.add_new((0x9001, 0x0003), 'OB', public_bytes)
    auth_item1.add_new((0x9001, 0x0005), 'ST', s)
    auth_item1.add_new((0x9001, 0x0006), 'ST', hash_value_tag)
    auth_item1.add_new((0x9001, 0x0007), 'ST', hash_val)

    auth_item1 = segment_and_embed_hashes(image_data, auth_item1)
    auth_sequence.append(auth_item1)

    ds.BeamSequence = auth_sequence
    return ds



def encode_to_dicom(image_array, name, id, sex, age, ImaNum, Comments="", Physician=""):
    # 创建一个DICOM数据集
    file_meta = FileMetaDataset()
    sopInsUID = generate_uid(prefix=None)
    image_sop_instance = {}
    image_sop_instance['SOPInsUID'] = sopInsUID
    SOPClaUID = generate_uid()
    image_sop_instance['SOPClaUID'] = SOPClaUID
    image_sop_instance['TransferSyntax'] = "1.2.840.10008.1.2.1"

    file_meta.MediaStorageSOPClassUID = generate_uid()
    file_meta.MediaStorageSOPInstanceUID = sopInsUID
    file_meta.ImplementationClassUID = UID("1.2.3.4")

    path = "./ImageStoragePath" + '\\' + '{}.dcm'.format(sopInsUID)
    filename_little_endian = path
    ds = FileDataset(filename_little_endian, {}, file_meta=file_meta, preamble=b"\0" * 128)
    # 设置DICOM标签值
    ds.PatientName = name
    ds.PatientID = str(id)
    ds.PatientSex = sex
    ds.PatientAge = str(age).zfill(3) + 'Y'
    ds.PerformingPhysicianName = Comments
    ds.ImageComments = Physician
    ds.Modality = "SC"

    # 将图像数据转换为8位整数类型
    scaled_result = image_array.astype(np.uint8)
    # 将图像数据保存到DICOM数据集中
    pixel_data_element = DataElement(0x7fe00010, 'OW', scaled_result.tobytes())
    ds.add(pixel_data_element)

    ds.SOPInstanceUID = sopInsUID

    ds.Rows = scaled_result.shape[0]
    ds.Columns = scaled_result.shape[1]
    ds.PhotometricInterpretation = "MONOCHROME1"
    ds.SamplesPerPixel = 1
    ds.BitsStored = 8
    ds.BitsAllocated = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.PlanarConfiguration = 1

    #Add the time
    dt = datetime.datetime.now()
    ds.ContentDate = time.strftime('%Y%m%d')
    timeStr = dt.strftime("%H%M%S.%f")
    ds.ContentTime = timeStr
    ds.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRBigEndian
    ds.is_little_endian = True
    ds.is_implicit_VR = True

    #加密文件
    ds = entropy(ds, scaled_result, tags=["PatientID"])
    # 保存DICOM数据集为文件
    ds.save_as(filename_little_endian)
    image_sop_instance['StoragePath'] = filename_little_endian
    print("DICOM文件保存成功！")

    return image_sop_instance




if __name__ == "__main__":
    image_array = np.random.randint(0, 255, size=(512, 512))  # 替换为实际的图像数组
    name = "tyd"

    # 调用函数将图像编码为DICOM并保存为文件
    encode_to_dicom(image_array, name, id="1111", sex="M", age="18",ImaNum=0,Comments="", Physician="")