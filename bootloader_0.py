import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import serial
import serial.tools.list_ports
import threading
import time
import struct

class BootloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("STM32 UART Bootloader Tool")
        self.root.geometry("800x600")
        
        self.serial_port = None
        self.connected = False
        
        self.setup_ui()
        self.refresh_ports()
        
    def setup_ui(self):
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 串口設置區域
        port_frame = ttk.LabelFrame(main_frame, text="串口設置", padding="5")
        port_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(port_frame, text="串口:").grid(row=0, column=0, padx=5)
        self.port_combo = ttk.Combobox(port_frame, width=15)
        self.port_combo.grid(row=0, column=1, padx=5)
        
        ttk.Label(port_frame, text="波特率:").grid(row=0, column=2, padx=5)
        self.baud_combo = ttk.Combobox(port_frame, values=['115200', '57600', '38400', '19200', '9600'])
        self.baud_combo.set('115200')
        self.baud_combo.grid(row=0, column=3, padx=5)
        
        ttk.Button(port_frame, text="刷新", command=self.refresh_ports).grid(row=0, column=4, padx=5)
        self.connect_btn = ttk.Button(port_frame, text="連接", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=5, padx=5)
        
        # 設備信息區域
        info_frame = ttk.LabelFrame(main_frame, text="設備信息", padding="5")
        info_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Button(info_frame, text="讀取Chip ID", command=self.read_chip_id).grid(row=0, column=0, padx=5)
        ttk.Button(info_frame, text="讀取版本", command=self.read_version).grid(row=0, column=1, padx=5)
        
        self.chip_id_var = tk.StringVar(value="未知")
        self.version_var = tk.StringVar(value="未知")
        ttk.Label(info_frame, text="Chip ID:").grid(row=1, column=0, padx=5, sticky=tk.W)
        ttk.Label(info_frame, textvariable=self.chip_id_var).grid(row=1, column=1, padx=5, sticky=tk.W)
        ttk.Label(info_frame, text="版本:").grid(row=2, column=0, padx=5, sticky=tk.W)
        ttk.Label(info_frame, textvariable=self.version_var).grid(row=2, column=1, padx=5, sticky=tk.W)
        
        # 操作區域
        operation_frame = ttk.LabelFrame(main_frame, text="Flash操作", padding="5")
        operation_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # 文件選擇
        ttk.Label(operation_frame, text="文件:").grid(row=0, column=0, padx=5, sticky=tk.W)
        self.file_path_var = tk.StringVar()
        ttk.Entry(operation_frame, textvariable=self.file_path_var, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(operation_frame, text="瀏覽", command=self.browse_file).grid(row=0, column=2, padx=5)
        
        # 地址設置
        ttk.Label(operation_frame, text="地址:").grid(row=1, column=0, padx=5, sticky=tk.W)
        self.address_var = tk.StringVar(value="0x08008000")
        ttk.Entry(operation_frame, textvariable=self.address_var, width=20).grid(row=1, column=1, padx=5, sticky=tk.W)
        
        # 新增長度設置
        ttk.Label(operation_frame, text="長度:").grid(row=1, column=2, padx=5, sticky=tk.W)
        self.length_var = tk.StringVar(value="0x100")
        ttk.Entry(operation_frame, textvariable=self.length_var, width=10).grid(row=1, column=3, padx=5, sticky=tk.W)
        
        # 操作按鈕
        btn_frame = ttk.Frame(operation_frame)
        btn_frame.grid(row=2, column=0, columnspan=4, pady=10)
        
        ttk.Button(btn_frame, text="擦除", command=self.erase_flash).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="寫入", command=self.write_flash).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="讀取", command=self.read_flash).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="跳轉執行", command=self.jump_to_app).pack(side=tk.LEFT, padx=5)
        # 在 setup_ui 函數的 info_frame 部分添加
        ttk.Button(info_frame, text="重新連接", command=self.reconnect_bootloader).grid(row=0, column=5, padx=5)
        
        # 進度條
        self.progress = ttk.Progressbar(main_frame, mode='determinate')
        self.progress.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # 狀態訊息區域
        status_frame = ttk.LabelFrame(main_frame, text="狀態訊息", padding="5")
        status_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        # 清除按鈕
        self.clear_btn = ttk.Button(status_frame, text="清除日誌", command=self.clear_log)
        self.clear_btn.pack(anchor="ne", pady=(0, 5))

        # 狀態訊息文本框
        self.status_text = scrolledtext.ScrolledText(status_frame, height=15, width=80)
        self.status_text.pack(fill=tk.BOTH, expand=True)

        
        # 配置網格權重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(4, weight=1)
 
    def clear_log(self):
        """清除狀態訊息日誌"""
        try:
            self.status_text.delete(1.0, tk.END)
            self.log_message("日誌已清除")
        except Exception as e:
            print(f"清除日誌錯誤: {e}")
 
        
    def log_message(self, message):
        """添加訊息到狀態窗口"""
        timestamp = time.strftime("%H:%M:%S")
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.status_text.see(tk.END)
        self.root.update()
        
    def refresh_ports(self):
        """刷新串口列表 (確保映射正確)"""
        ports_info = []
        port_values = []
        
        for port in serial.tools.list_ports.comports():
            # 構建詳細的設備信息
            device_info = []
            
            # 設備描述
            if port.description and port.description != 'n/a':
                desc = port.description
                if port.device in desc:
                    desc = desc.replace(f"({port.device})", "").strip()
                if desc and desc != port.device:
                    device_info.append(desc)
            
            # 製造商信息
            if port.manufacturer and port.manufacturer != 'n/a':
                device_info.append(f"[{port.manufacturer}]")
            
            # VID:PID 信息
            if port.vid and port.pid:
                device_info.append(f"VID:{port.vid:04X} PID:{port.pid:04X}")
            
            # 組合顯示文本：COM口 - 其他信息
            if device_info:
                display_text = f"{port.device} - {' - '.join(device_info)}"
            else:
                display_text = port.device
            
            ports_info.append(display_text)
            port_values.append(port.device)  # 確保這裡只儲存純COM口名稱
        
        # 更新下拉選單
        self.port_combo['values'] = ports_info
        
        # 建立映射關係
        self.port_mapping = dict(zip(ports_info, port_values))
        
        # 調試信息
        self.log_message(f"串口映射關係:")
        for display, actual in self.port_mapping.items():
            self.log_message(f"  {display} -> {actual}")
        
        if ports_info:
            self.port_combo.set(ports_info[0])
            
        self.log_message(f"找到 {len(ports_info)} 個串口設備")
            
    def clear_device_info(self):
        """清空設備信息"""
        self.chip_id_var.set("未知")
        self.version_var.set("未知")
        self.log_message("設備信息已清空")

    def toggle_connection(self):
        """切換連接狀態"""
        if not self.connected:
            try:
                # 獲取選中的顯示文本
                selected_display = self.port_combo.get()
                
                # 正確提取COM口名稱
                if hasattr(self, 'port_mapping') and selected_display in self.port_mapping:
                    port = self.port_mapping[selected_display]
                else:
                    # 使用正則表達式提取COM口
                    import re
                    com_match = re.match(r'(COM\d+)', selected_display)
                    if com_match:
                        port = com_match.group(1)
                    else:
                        # 備用方法
                        if ' - ' in selected_display:
                            port = selected_display.split(' - ')[0].strip()
                        elif '(' in selected_display:
                            port = selected_display.split('(')[0].strip()
                        else:
                            port = selected_display.strip()
                
                baud = int(self.baud_combo.get())
                self.serial_port = serial.Serial(port, baud, timeout=1)
                self.connected = True
                self.connect_btn.config(text="斷開")
                self.log_message(f"已連接到 {port} @ {baud}")
                self.log_message(f"設備: {selected_display}")
            except Exception as e:
                messagebox.showerror("錯誤", f"連接失敗: {str(e)}")
        else:
            if self.serial_port:
                self.serial_port.close()
            self.connected = False
            self.connect_btn.config(text="連接")
            self.log_message("已斷開連接")
            
            # 清空設備信息
            self.clear_device_info()
            
    def send_command(self, command, data=None):
        """發送命令到Bootloader"""
        if not self.connected:
            messagebox.showerror("錯誤", "請先連接串口")
            return None
            
        try:
            # 發送命令
            self.serial_port.write(bytes([command]))
            
            # 等待ACK
            response = self.serial_port.read(1)
            if len(response) == 0 or response[0] != 0x79:
                self.log_message(f"命令 0x{command:02X} 未收到ACK")
                return None
                
            # 發送數據(如果有)
            if data:
                self.serial_port.write(data)
                
            return True
            
        except Exception as e:
            self.log_message(f"發送命令錯誤: {str(e)}")
            return None
            
    def read_chip_id(self):
        """讀取芯片ID (增強版)"""
        try:
            # 先檢查連接狀態
            if not self.check_bootloader_alive():
                self.log_message("Bootloader連接已斷開，嘗試重新連接...")
                if not self.reconnect_bootloader():
                    return
                    
            self.get_custom_chip_id()
            
        except Exception as e:
            self.log_message(f"讀取芯片ID錯誤: {str(e)}")
            self.serial_port.write(b'\xFF\xFF')  # 擦除所有扇區
                
    def read_version(self):
        """讀取版本 (增強版)"""
        try:
            # 先檢查連接狀態
            if not self.check_bootloader_alive():
                self.log_message("Bootloader連接已斷開，嘗試重新連接...")
                if not self.reconnect_bootloader():
                    return
                    
            self.get_custom_version()
        
        except Exception as e:
            self.log_message(f"讀取版本錯誤: {str(e)}")
                
    def browse_file(self):
        """瀏覽文件"""
        filename = filedialog.askopenfilename(
            title="選擇固件文件",
            filetypes=[("Binary files", "*.bin"), ("Hex files", "*.hex"), ("All files", "*.*")]
        )
        if filename:
            self.file_path_var.set(filename)
            
    def erase_flash(self):
        """擦除Flash"""
        def erase_thread():
            try:
                self.log_message("開始擦除Flash...")
                self.progress['value'] = 0
                
                # 發送擦除命令
                if self.send_command(0x44):  # CMD_ERASE_MEMORY
                    # 發送擦除扇區數量 (擦除所有應用程序區域)
                    num_sectors = 6  # 擦除扇區2-7
                    checksum = 0xFF ^ num_sectors
                    data = bytes([num_sectors, checksum])
                    
                    self.serial_port.write(data)
                    
                    # 等待擦除完成 (可能需要較長時間)
                    self.log_message("等待擦除完成...")
                    response = self.serial_port.read(1)
                    if len(response) == 1 and response[0] == 0x79:
                        self.log_message("Flash擦除完成")
                        self.progress['value'] = 100
                    else:
                        self.log_message("Flash擦除失敗")
                        
            except Exception as e:
                self.log_message(f"擦除錯誤: {str(e)}")
                
        threading.Thread(target=erase_thread, daemon=True).start()

    def get_custom_version(self):
        """獲取自定義Bootloader版本 (增強版)"""
        try:
            # 清空緩衝區
            self.serial_port.reset_input_buffer()
            
            # 發送GET_VERSION命令 (0x01)
            self.serial_port.write(bytes([0x01]))
            self.log_message("發送GET_VERSION命令: 0x01")
            
            # 等待ACK (增加重試機制)
            for retry in range(3):
                response = self.serial_port.read(1)
                if len(response) == 1 and response[0] == 0x79:
                    break
                elif retry < 2:
                    self.log_message(f"重試獲取版本 {retry + 1}/3")
                    time.sleep(0.1)
                    self.serial_port.write(bytes([0x01]))
                else:
                    self.log_message(f"版本命令ACK失敗: {response.hex() if response else 'None'}")
                    return False
                    
            self.log_message("版本命令收到ACK")
            
            # 讀取版本號
            version = self.serial_port.read(1)
            if len(version) == 1:
                # 修正這裡：正確定義 version_str
                version_num = version[0]
                version_str = f"v{version_num/16:.1f}"  # 這裡定義 version_str
                self.log_message(f"Bootloader版本: {version_str}")
                self.version_var.set(version_str)  # 設置版本顯示
                
                # 等待最終ACK
                final_ack = self.serial_port.read(1)
                if len(final_ack) == 1 and final_ack[0] == 0x79:
                    self.log_message("版本讀取完成")
                    return True
                else:
                    self.log_message(f"最終ACK失敗: {final_ack.hex() if final_ack else 'None'}")
                    return False
            else:
                self.log_message("版本號讀取失敗")
                return False
                
        except Exception as e:
            self.log_message(f"獲取版本錯誤: {str(e)}")
            return False


    def get_custom_chip_id(self):
        """獲取自定義Bootloader芯片ID (增強版)"""
        try:
            # 清空緩衝區
            self.serial_port.reset_input_buffer()
            
            # 發送GET_ID命令 (0x02)
            self.serial_port.write(bytes([0x02]))
            self.log_message("發送GET_ID命令: 0x02")
            
            # 等待ACK (增加重試機制)
            for retry in range(3):
                response = self.serial_port.read(1)
                if len(response) == 1 and response[0] == 0x79:
                    break
                elif retry < 2:
                    self.log_message(f"重試獲取芯片ID {retry + 1}/3")
                    time.sleep(0.1)
                    self.serial_port.write(bytes([0x02]))
                else:
                    self.log_message(f"芯片ID命令ACK失敗: {response.hex() if response else 'None'}")
                    return False
                    
            self.log_message("芯片ID命令收到ACK")
            
            # 讀取4字節芯片ID
            chip_id_bytes = self.serial_port.read(4)
            if len(chip_id_bytes) != 4:
                self.log_message(f"芯片ID讀取失敗，只收到 {len(chip_id_bytes)} 字節")
                return False
                
            # 組合芯片ID (大端序)
            chip_id = (chip_id_bytes[0] << 24) | (chip_id_bytes[1] << 16) | \
                    (chip_id_bytes[2] << 8) | chip_id_bytes[3]
                    
            self.log_message(f"芯片ID: 0x{chip_id:08X}")
            
            # 根據芯片ID顯示芯片型號
            chip_name = self.get_chip_name(chip_id)
            self.log_message(f"芯片型號: {chip_name}")
            self.chip_id_var.set(f"0x{chip_id:08X} ({chip_name})")
            
            # 等待最終ACK
            final_ack = self.serial_port.read(1)
            if len(final_ack) == 1 and final_ack[0] == 0x79:
                self.log_message("芯片ID讀取完成")
                return True
            else:
                self.log_message(f"最終ACK失敗: {final_ack.hex() if final_ack else 'None'}")
                return False
                
        except Exception as e:
            self.log_message(f"獲取芯片ID錯誤: {str(e)}")
            return False

    def get_chip_name(self, chip_id):
        """根據芯片ID返回芯片名稱"""
        chip_dict = {
            0x0413: "STM32F405/407/415/417",
            0x0419: "STM32F42x/43x", 
            0x0431: "STM32F411",
            0x0441: "STM32F412",
            0x0463: "STM32F413/423",
            0x0434: "STM32F469/479",
            0x0421: "STM32F446",
            0x0423: "STM32F401xB/C",
            0x0433: "STM32F401xD/E",
            # 添加更多芯片ID
        }
        
        return chip_dict.get(chip_id, f"未知芯片")


    def check_bootloader_alive(self):
        """檢查Bootloader是否還活著"""
        try:
            if not self.connected or not self.serial_port:
                return False
                
            # 發送簡單的版本查詢命令來檢查連接
            self.serial_port.reset_input_buffer()
            self.serial_port.write(bytes([0x01]))  # GET_VERSION
            
            # 等待ACK，超時時間短一些
            response = self.serial_port.read(1)
            if len(response) == 1 and response[0] == 0x79:
                # 讀取版本號並丟棄
                self.serial_port.read(1)
                # 讀取最終ACK並丟棄
                self.serial_port.read(1)
                return True
            else:
                return False
                
        except Exception:
            return False
        
    def reconnect_bootloader(self):
        """重新連接Bootloader (增強版)"""
        try:
            self.log_message("嘗試重新連接Bootloader...")
            
            # 關閉現有連接
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
                self.log_message("已關閉現有連接")
                
            time.sleep(0.5)
            
            # 獲取實際的COM口名稱
            selected_display = self.port_combo.get()
            self.log_message(f"選中的顯示文本: {selected_display}")
            
            # 提取實際的COM口名稱
            port = None
            
            # 方法1：從映射中獲取
            if hasattr(self, 'port_mapping') and selected_display in self.port_mapping:
                port = self.port_mapping[selected_display]
                self.log_message(f"從映射獲取串口: {port}")
            else:
                # 方法2：解析顯示文本
                import re
                # 使用正則表達式匹配COM口
                com_match = re.match(r'(COM\d+)', selected_display)
                if com_match:
                    port = com_match.group(1)
                    self.log_message(f"從文本解析串口: {port}")
                else:
                    # 方法3：手動分割
                    if ' - ' in selected_display:
                        port = selected_display.split(' - ')[0].strip()
                    elif '(' in selected_display:
                        port = selected_display.split('(')[0].strip()
                    else:
                        port = selected_display.strip()
                    self.log_message(f"手動分割獲取串口: {port}")
            
            if not port:
                raise Exception("無法解析串口名稱")
                
            # 驗證串口名稱格式
            if not port.startswith('COM'):
                raise Exception(f"無效的串口名稱: {port}")
                
            self.log_message(f"準備連接串口: {port}")
            
            baud = int(self.baud_combo.get())
            self.serial_port = serial.Serial(port, baud, timeout=1)
            
            self.log_message(f"串口已開啟: {port} @ {baud}")
            
            # 測試連接
            if self.check_bootloader_alive():
                self.log_message("重新連接成功")
                return True
            else:
                self.log_message("Bootloader 測試失敗")
                return False
                
        except Exception as e:
            self.log_message(f"重新連接錯誤: {str(e)}")
            return False
                
    def write_flash(self):
        """寫入Flash"""
        def write_thread():
            try:
                file_path = self.file_path_var.get()
                if not file_path:
                    messagebox.showerror("錯誤", "請選擇要寫入的文件")
                    return
                    
                address_str = self.address_var.get()
                try:
                    address = int(address_str, 16) if address_str.startswith('0x') else int(address_str)
                except ValueError:
                    messagebox.showerror("錯誤", "地址格式錯誤")
                    return
                    
                # 讀取文件
                with open(file_path, 'rb') as f:
                    data = f.read()
                    
                self.log_message(f"開始寫入 {len(data)} 字節到地址 0x{address:08X}")
                
                # 分塊寫入 (每次最多256字節)
                chunk_size = 256
                total_chunks = (len(data) + chunk_size - 1) // chunk_size
                
                for i in range(total_chunks):
                    start_idx = i * chunk_size
                    end_idx = min(start_idx + chunk_size, len(data))
                    chunk = data[start_idx:end_idx]
                    chunk_addr = address + start_idx
                    
                    if self.write_memory_chunk(chunk_addr, chunk):
                        progress = (i + 1) * 100 // total_chunks
                        self.progress['value'] = progress
                        self.log_message(f"寫入進度: {progress}% ({i+1}/{total_chunks})")
                    else:
                        self.log_message(f"寫入失敗在地址 0x{chunk_addr:08X}")
                        return
                        
                self.log_message("Flash寫入完成")
                
            except Exception as e:
                self.log_message(f"寫入錯誤: {str(e)}")
                
        threading.Thread(target=write_thread, daemon=True).start()

    def write_memory_chunk(self, address, data):
        """寫入單個記憶體塊"""
        try:
            # 發送寫入命令
            if not self.send_command(0x31):  # CMD_WRITE_MEMORY
                return False
                
            # 發送地址
            addr_bytes = struct.pack('>I', address)  # 大端序
            addr_checksum = 0
            for b in addr_bytes:
                addr_checksum ^= b
                
            self.serial_port.write(addr_bytes + bytes([addr_checksum]))
            
            # 等待ACK
            response = self.serial_port.read(1)
            if len(response) == 0 or response[0] != 0x79:
                return False
                
            # 發送數據長度和數據
            length = len(data) - 1  # N = 數據字節數 - 1
            data_to_send = bytes([length]) + data
            
            # 計算校驗和
            checksum = 0
            for b in data_to_send:
                checksum ^= b
                
            self.serial_port.write(data_to_send + bytes([checksum]))
            
            # 等待最終ACK
            response = self.serial_port.read(1)
            return len(response) == 1 and response[0] == 0x79
            
        except Exception as e:
            self.log_message(f"寫入塊錯誤: {str(e)}")
            return False
        
    def read_memory(self, address, length):
        """讀取記憶體 - 可重用的函數"""
        try:
            max_read_size = 256  # STM32 bootloader最大一次讀取256字節
            all_data = bytearray()
            remaining = length
            current_addr = address
            
            while remaining > 0:
                # 計算本次讀取大小
                read_size = min(remaining, max_read_size)
                
                # 發送讀取命令
                if not self.send_command(0x11):  # CMD_READ_MEMORY
                    raise Exception(f"讀取命令失敗 @ 0x{current_addr:08X}")
                    
                # 發送地址
                addr_bytes = struct.pack('>I', current_addr)
                addr_checksum = 0
                for b in addr_bytes:
                    addr_checksum ^= b
                    
                self.serial_port.write(addr_bytes + bytes([addr_checksum]))
                
                # 等待ACK
                ack = self.serial_port.read(1)
                if len(ack) == 0 or ack[0] != 0x79:
                    raise Exception(f"地址ACK失敗 @ 0x{current_addr:08X}")
                    
                # 發送長度 (N-1格式)
                length_byte = read_size - 1
                checksum = 0xFF ^ length_byte
                self.serial_port.write(bytes([length_byte, checksum]))
                
                # 等待ACK
                ack = self.serial_port.read(1)
                if len(ack) == 0 or ack[0] != 0x79:
                    raise Exception(f"長度ACK失敗 @ 0x{current_addr:08X}")
                    
                # 讀取數據
                data = self.serial_port.read(read_size)
                if len(data) != read_size:
                    raise Exception(f"數據讀取不完整 @ 0x{current_addr:08X}")
                
                all_data.extend(data)
                current_addr += read_size
                remaining -= read_size
                
            return all_data
            
        except Exception as e:
            self.log_message(f"讀取錯誤: {str(e)}")
            return None
            
    def read_flash(self):
        """讀取Flash"""
        try:
            # 獲取地址
            address_str = self.address_var.get()
            address = int(address_str, 16) if address_str.startswith('0x') else int(address_str)
            
            # 獲取長度
            length_str = self.length_var.get()
            try:
                length = int(length_str, 16) if length_str.startswith('0x') else int(length_str)
                # 確保長度不超過STM32 bootloader的限制
                if length > 256:
                    self.log_message(f"警告: 長度 {length} 超過單次讀取限制，將分多次讀取")
            except ValueError:
                self.log_message(f"長度格式錯誤: {length_str}，使用預設值0x100")
                length = 0x100
            
            self.log_message(f"開始從地址 0x{address:08X} 讀取 {length} 字節...")
            
            # 如果長度超過256，使用read_memory函數分段讀取
            if length > 256:
                data = self.read_memory(address, length)
                if data:
                    # 將數據轉換為更易讀的格式並顯示
                    bytes_per_line = 16
                    
                    for i in range(0, len(data), bytes_per_line):
                        chunk = data[i:i+bytes_per_line]
                        line = ", ".join([f"{b:02X}" for b in chunk])
                        self.log_message(f"0x{address + i*bytes_per_line:08X}: {line}")
                        
                    self.log_message(f"讀取完成，共 {len(data)} 字節")
                else:
                    self.log_message("讀取失敗")
            else:
                # 對於小於256字節的數據，使用單次讀取
                if self.read_memory_chunk(address, length - 1):  # STM32 bootloader使用N-1格式
                    self.log_message(f"從地址 0x{address:08X} 讀取 {length} 字節完成")
                else:
                    self.log_message("讀取失敗")
                
        except Exception as e:
            self.log_message(f"讀取錯誤: {str(e)}")

    def read_memory_chunk(self, address, length):
        """讀取單個記憶體塊"""
        try:
            # 發送讀取命令
            if not self.send_command(0x11):  # CMD_READ_MEMORY
                return False
                
            # 發送地址
            addr_bytes = struct.pack('>I', address)  # 大端序
            addr_checksum = 0
            for b in addr_bytes:
                addr_checksum ^= b
                
            self.serial_port.write(addr_bytes + bytes([addr_checksum]))
            
            # 等待ACK
            response = self.serial_port.read(1)
            if len(response) == 0 or response[0] != 0x79:
                return False
                
            # 發送長度
            length_checksum = 0xFF ^ length
            self.serial_port.write(bytes([length, length_checksum]))
            
            # 等待ACK
            response = self.serial_port.read(1)
            if len(response) == 0 or response[0] != 0x79:
                return False
                
            # 讀取數據
            data = self.serial_port.read(length + 1)
            if len(data) == length + 1:
                # 將數據轉換為更易讀的格式：每個字節後面加逗號和空格，每16個字節換行
                bytes_per_line = 16
                
                for i in range(0, len(data), bytes_per_line):
                    chunk = data[i:i+bytes_per_line]
                    line = ", ".join([f"{b:02X}" for b in chunk])
                    self.log_message(f"0x{address + i*bytes_per_line:08X}: {line}")
                    
                return True
            else:
                return False
                
        except Exception as e:
            self.log_message(f"讀取塊錯誤: {str(e)}")
            return False

    # APP起始地址
    APP_START_ADDRESS = 0x08008000
                
    def jump_to_app(self):
        """跳轉到應用程序"""
        try:
            self.log_message("正在跳轉到APP...")

            # 發送Go命令
            if not self.send_command(0x21):  # CMD_GO
                self.log_message("發送Go命令失敗")
                return

            # 發送APP起始地址 (大端序)
            addr_bytes = [
                (self.APP_START_ADDRESS >> 24) & 0xFF,
                (self.APP_START_ADDRESS >> 16) & 0xFF,
                (self.APP_START_ADDRESS >> 8) & 0xFF,
                self.APP_START_ADDRESS & 0xFF
            ]

            # 計算校驗和
            checksum = 0
            for byte in addr_bytes:
                checksum ^= byte

            # 發送地址和校驗和
            self.serial_port.write(bytes(addr_bytes + [checksum]))

            self.log_message("跳轉命令發送成功！")
            self.log_message("請檢查串口輸出是否有APP啟動訊息...")

        except Exception as e:
            self.log_message(f"跳轉失敗: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = BootloaderGUI(root)
    root.mainloop()