from pyspark.sql import SparkSession
from pyspark.sql.functions import col, regexp_replace, monotonically_increasing_id
from pyspark.sql import functions as F
from pyspark.sql.types import LongType
from pyspark.sql.functions import col, to_date
from pyspark.sql.types import IntegerType, FloatType, LongType

# Khởi tạo phiên Spark với MongoDB và PostgreSQL

spark = SparkSession.builder \
    .appName("Spark with MongoDB and PostgreSQL") \
    .config("spark.jars.packages", "org.mongodb.spark:mongo-spark-connector_2.12:3.0.1,org.postgresql:postgresql:42.7.4") \
    .config("spark.mongodb.read.connection.uri", "mongodb://mymongodb:27017/db_BDS.coll_BDS") \
    .getOrCreate()
# Cài đặt mức độ log

spark.sparkContext.setLogLevel("INFO")

# Đọc dữ liệu từ MongoDB vào DataFrame

df = spark.read \
    .format("mongo") \
    .option("uri", "mongodb://mymongodb:27017/db_BDS.coll_BDS") \
    .load()

df.show(5)
df.printSchema()
#Xóa các cột không cần thiết
df = df.drop("_id","Chi_tiet_link")
from pyspark.sql import functions as F

def remove_special_characters_pyspark(df, text_column):
    # Xử lý biểu tượng emoji và ký tự đặc biệt
    emoji_pattern = "[" \
        "\U0001F600-\U0001F64F"  \
        "\U0001F300-\U0001F5FF"  \
        "\U0001F680-\U0001F6FF"  \
        "\U0001F1E0-\U0001F1FF"  \
        "\u2600-\u26FF"  \
        "\u2700-\u27BF"  \
        "]"
    
    # Loại bỏ emoji
    df = df.withColumn(text_column, F.regexp_replace(text_column, emoji_pattern, ""))
    
    # Loại bỏ các ký tự đặc biệt, chỉ giữ lại các ký tự tiếng Việt, chữ cái, số, khoảng trắng và dấu câu cơ bản
    allowed_chars = r'[^a-zA-Z0-9\s.,áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴĐ]'
    
    df = df.withColumn(text_column, F.regexp_replace(text_column, allowed_chars, ""))
    
    return df
# Giả sử DataFrame có cột 'text' chứa dữ liệu văn bản
df=remove_special_characters_pyspark(df, 'Mô_tả')
df=remove_special_characters_pyspark(df, 'Tiêu_đề')

def remove_text_pyspark(df, text_column):
    # Loại bỏ tất cả ký tự không phải là chữ số
    df = df.withColumn(text_column, F.regexp_replace(text_column, r'[^\d]', ''))
    return df
df=remove_text_pyspark(df,'Diện_tích')
df=remove_text_pyspark(df,'Số_phòng_ngủ')
df=remove_text_pyspark(df,'Số_phòng_toilet')

# Lọc các hàng có giá trị không phải là số trong cột 'Diện_tích'
non_numeric_dien_tich = df.filter(F.col('Diện_tích').rlike(r'[^\d]'))

# Lọc các hàng có giá trị không phải là số trong cột 'Số_phòng_ngủ'
non_numeric_so_phong_ngu = df.filter(F.col('Số_phòng_ngủ').rlike(r'[^\d]'))

# Lọc các hàng có giá trị không phải là số trong cột 'Số_phòng_toilet'
non_numeric_so_phong_toilet = df.filter(F.col('Số_phòng_toilet').rlike(r'[^\d]'))

# Định nghĩa hàm xử lý giá
def xu_ly_gia(price_str):
    if price_str is None:  # Kiểm tra giá trị None
        return 0  # Hoặc bạn có thể trả về một giá trị khác nếu cần

    units = {
        'tỷ': 1000000000,
        'triệu': 1000000,
        'nghìn': 1000,
    }

    total = 0
    current_value = 0
    parts = price_str.split()
    
    for part in parts:
        if part in units:
            total += current_value * units[part]
            current_value = 0
        else:
            try:
                current_value = int(part)
            except ValueError:
                current_value = 0  # Trường hợp không thể chuyển đổi
    total += current_value
    return total

# Chuyển hàm Python thành UDF trong PySpark
xu_ly_gia_udf = F.udf(xu_ly_gia, LongType())  # Sử dụng LongType để tương thích

# Áp dụng UDF lên cột 'Giá' trong DataFrame và thay đổi cột 'Giá'
df = df.withColumn('Giá', xu_ly_gia_udf(F.col('Giá')))

# Chuyển đổi kiểu dữ liệu
df = df.withColumn("Diện_tích", col("Diện_tích").cast(FloatType())) \
       .withColumn("Giá", col("Giá").cast(LongType()))\
       .withColumn("Số_phòng_ngủ", col("Số_phòng_ngủ").cast(IntegerType())) \
       .withColumn("Số_phòng_toilet", col("Số_phòng_toilet").cast(IntegerType())) \
       .withColumn("Ngày_đăng", to_date(col("Ngày_đăng"), "dd/MM/yyyy"))

# Tích hợp phần trước ký tự '/' trong cột 'Pháp_lý'
df = df.withColumn('Pháp_lý', F.split(F.col('Pháp_lý'), '/').getItem(0))
distinct_phap_ly_values = df.select('Pháp_lý').distinct()


# Xử Lý giá trị null cột Diện_tích
# Thay thế NULL bằng giá trị trung vị
median_area = df.approxQuantile("Diện_tích", [0.5], 0)[0]
df = df.fillna({"Diện_tích": median_area})

#xử lý giá trị null của Số_phòng_ngủ và Số_phòng_toilet bằng 0
df = df.fillna({"Số_phòng_ngủ": 0, "Số_phòng_toilet": 0})
df.show()

#Thay thế giá trị null của Pháp_lý thành "Unknown"
df = df.fillna({"Pháp_lý": "Unknown"})
df.show()

# Xóa các dòng có giá trị bằng 0 trong cột 'Giá'
df = df.filter(F.col("Giá") != 0)

# đổi tên cột
df = df \
    .withColumnRenamed("Diện_tích", "Area") \
    .withColumnRenamed("Mã_tin", "ID") \
    .withColumnRenamed("Giá", "Price") \
    .withColumnRenamed("Mô_tả", "Description") \
    .withColumnRenamed("Ngày_đăng", "Posted_Date") \
    .withColumnRenamed("Pháp_lý", "Legal_Status") \
    .withColumnRenamed("Quận", "District") \
    .withColumnRenamed("Số_phòng_ngủ", "Bedrooms") \
    .withColumnRenamed("Số_phòng_toilet", "Bathrooms") \
    .withColumnRenamed("Thành_phố", "City_Province") \
    .withColumnRenamed("Tiêu_đề", "Title") \
    .withColumnRenamed("Đường", "Street_Name")

# Lọc và giữ lại các dòng mà cột 'Legal_Status' không chứa giá trị 'Unknown'
df = df.filter(col("Legal_Status") != "Unknown")

# 1. Tạo bảng House_Info: Thông tin về diện tích, giá, số phòng
house_info = df.select(
    F.col("ID").alias("House_ID"),  # Sử dụng cột ID làm khóa chính
    F.col("Area").alias("Area"),
    F.col("Price").alias("Price"),
    F.col("Title").alias("Title"),
    F.col("Description").alias("Description"),
).dropDuplicates(["House_ID"])  # Đảm bảo không có bản ghi trùng lặp

# 2. Tạo bảng house_rooom: Thông tin về phòng
house_room = df.select(
    F.col("ID").alias("House_ID"),  # Sử dụng cột ID làm khóa ngoại
    F.col("Bedrooms").alias("Bedrooms"),
    F.col("Bathrooms").alias("Bathrooms"),
).withColumn("house_room_ID", F.monotonically_increasing_id()) # Sử dụng làm khóa chính

# 3. Tạo bảng Transaction: Chứa thông tin giao dịch
house_transaction = df.select(
    F.col("ID").alias("House_ID"),  # Sử dụng cột ID làm khóa ngoại
    F.col("Posted_Date").alias("Posted_Date"),
    F.col("Legal_Status").alias("Legal_Status"),
    F.col("District").alias("District_Name"), 
    F.col("City_Province").alias("City_Province_Name"),
    F.col("Street_Name").alias("Street_Name") 
).withColumn("Transaction_ID", F.monotonically_increasing_id())  # Tạo Transaction_ID làm khóa chính

#      đưa lên postgres
#jdbc_url = "jdbc:postgresql://host.docker.internal:5432/database_bds"
jdbc_url = "jdbc:postgresql://mypostgres:5432/database"

# Kết nối tới PostgreSQL
connection_properties = {
    "user": "postgres",
    "password": "postgres",
    "driver": "org.postgresql.Driver"
}

#hàm ghi vô postgres
def write_to_postgres(df, table_name):
    try:
        df.write.jdbc(
            url=jdbc_url,
            table=table_name,
            mode="overwrite",
            properties=connection_properties
        )
        print(f"Đã ghi thành công bảng {table_name} vào PostgreSQL!")
    except Exception as e:
        print(f"Lỗi khi ghi bảng {table_name} vào PostgreSQL: {e}")

#Lưu bảng vào PostgreSQL
write_to_postgres(house_info, "house_info")
write_to_postgres(house_room, "house_room")
write_to_postgres(house_transaction, "house_transaction")

# Ghi dữ liệu đã xử lý vào MongoDB
df.write \
    .format("mongo") \
    .option("uri", "mongodb://mymongodb:27017") \
    .option("database", "db_BDS_cleaned") \
    .option("collection", "coll_BDS_cleaned") \
    .mode("overwrite") \
    .save()