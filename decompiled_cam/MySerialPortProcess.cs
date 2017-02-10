using CAMV2.Core.XMLRecord;
using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Ports;
using System.Linq;
using System.Management;
using System.Threading;

namespace MyProtocol
{
	public class MySerialPortProcess
	{
		public static System.Collections.Generic.Dictionary<string, SerialPort> SerialPortList = new System.Collections.Generic.Dictionary<string, SerialPort>();

		public static System.Collections.Generic.List<DevicePort> DevicePortList = new System.Collections.Generic.List<DevicePort>();

		public static System.Collections.Generic.List<DevicePort> PreviDevicePortList = new System.Collections.Generic.List<DevicePort>();

		public static System.Collections.Generic.Dictionary<int, string> DeviceDictionary = new System.Collections.Generic.Dictionary<int, string>();

		private static object _lock = new object();

		public static int PreviousPortCounts = 0;

		public static bool IfUpdatingFirmware = false;

		public static int WaitingCount = 0;

		public static void Initialize()
		{
			MySerialPortProcess.AddDeviceNumberToDictionary(31, "Grid");
			MySerialPortProcess.AddDeviceNumberToDictionary(32, "GridRevA");
			MySerialPortProcess.AddDeviceNumberToDictionary(33, "GridRev2");
			MySerialPortProcess.AddDeviceNumberToDictionary(1, "HuePlus");
		}

		public static void AddDeviceNumberToDictionary(int devcieNum, string deviceName)
		{
			if (MySerialPortProcess.DeviceDictionary.ContainsKey(devcieNum))
			{
				MySerialPortProcess.DeviceDictionary.Remove(devcieNum);
			}
			MySerialPortProcess.DeviceDictionary.Add(devcieNum, deviceName);
		}

		public static int ProductCounter(string deviceName)
		{
			int num = 0;
			foreach (DevicePort current in MySerialPortProcess.DevicePortList)
			{
				if (current.Device == deviceName)
				{
					num++;
				}
			}
			return num;
		}

		public static DevicePort ProductInListFinder(string deviceName, int which)
		{
			int num = 0;
			DevicePort result;
			foreach (DevicePort current in MySerialPortProcess.DevicePortList)
			{
				if (current.Device == deviceName)
				{
					num++;
					if (num == which)
					{
						result = current;
						return result;
					}
				}
			}
			result = new DevicePort
			{
				Device = null,
				PortName = null
			};
			return result;
		}

		public static bool IfDevicePortExists(System.Collections.Generic.List<DevicePort> DevicePortList, DevicePort device)
		{
			bool result;
			for (int i = 0; i < DevicePortList.Count; i++)
			{
				if (DevicePortList[i].Device == device.Device && DevicePortList[i].PortName == device.PortName)
				{
					result = true;
					return result;
				}
			}
			result = false;
			return result;
		}

		private static void CheckReplyValue(byte[] receiveBytes, byte[] replyBytes)
		{
			try
			{
				if (receiveBytes.Length == 5)
				{
					if (receiveBytes[0] / 64 == 3)
					{
						for (int i = 0; i < receiveBytes.Length; i++)
						{
							replyBytes[i] = receiveBytes[i];
						}
					}
				}
				else if (receiveBytes.Length == 1)
				{
					replyBytes[0] = receiveBytes[0];
				}
			}
			catch (System.Exception e)
			{
				ErrorXMLProcess.ExceptionProcess(e);
			}
		}

		public static System.Collections.Generic.List<object> GetPortFriendlyName()
		{
			System.Collections.Generic.List<object> result = null;
			try
			{
				using (ManagementObjectSearcher managementObjectSearcher = new ManagementObjectSearcher("SELECT * FROM WIN32_SerialPort"))
				{
					string[] portNames = SerialPort.GetPortNames();
					System.Collections.Generic.List<ManagementBaseObject> list = managementObjectSearcher.Get().Cast<ManagementBaseObject>().ToList<ManagementBaseObject>();
					list = list.FindAll((ManagementBaseObject x) => x["PNPDeviceID"].ToString().Contains("VID_04D8&PID_00DF&MI_00")).ToList<ManagementBaseObject>();
					result = (from n in portNames
					join p in list on n equals p["DeviceID"].ToString()
					select p["Caption"]).ToList<object>();
				}
			}
			catch (System.Exception e)
			{
				ErrorXMLProcess.ExceptionProcess(e);
			}
			return result;
		}

		private static void AddProductToList(byte[] receiveBytes, SerialPort TheSerialPort)
		{
			try
			{
				foreach (int current in MySerialPortProcess.DeviceDictionary.Keys)
				{
					if ((int)receiveBytes[0] == current)
					{
						MySerialPortProcess.DevicePortList.Add(new DevicePort
						{
							Device = MySerialPortProcess.DeviceDictionary[current],
							PortName = TheSerialPort.PortName,
							BaudRate = TheSerialPort.BaudRate
						});
						MySerialPortProcess.WaitingCount++;
						MySerialPortProcess.SerialPortList[TheSerialPort.PortName].DataReceived -= new SerialDataReceivedEventHandler(MySerialPortProcess.SerialPort_DataReceived);
					}
				}
			}
			catch (System.Exception e)
			{
				ErrorXMLProcess.ExceptionProcess(e);
			}
		}

		public static void InitialDetectPort()
		{
			try
			{
				MySerialPortProcess.PreviDevicePortList.Clear();
				MySerialPortProcess.DevicePortList.Clear();
				System.Collections.Generic.List<object> portFriendlyName = MySerialPortProcess.GetPortFriendlyName();
				using (System.Collections.Generic.List<object>.Enumerator enumerator = portFriendlyName.GetEnumerator())
				{
					while (enumerator.MoveNext())
					{
						string text = (string)enumerator.Current;
						try
						{
							string text2 = text;
							text2 = text2.Substring(text2.IndexOf("(") + 1);
							text2 = text2.Substring(0, text2.IndexOf(")"));
							MySerialPortProcess.SerialPortList.Add(text2, new SerialPort(text2, 4800));
							MySerialPortProcess.SerialPortList[text2].Open();
							MySerialPortProcess.SerialPortList[text2].DataReceived -= new SerialDataReceivedEventHandler(MySerialPortProcess.SerialPort_DataReceived);
							MySerialPortProcess.SerialPortList[text2].DataReceived += new SerialDataReceivedEventHandler(MySerialPortProcess.SerialPort_DataReceived);
						}
						catch (System.Exception e)
						{
							ErrorXMLProcess.ExceptionProcess(e);
						}
					}
				}
			}
			catch (System.Exception e)
			{
				ErrorXMLProcess.ExceptionProcess(e);
			}
		}

		public static void SerialPort_DataReceived(object sender, SerialDataReceivedEventArgs e)
		{
			try
			{
				SerialPort serialPort = (SerialPort)sender;
				int bytesToRead = serialPort.BytesToRead;
				byte[] array = new byte[bytesToRead];
				MySerialPortProcess.SerialPortList[serialPort.PortName].Read(array, 0, bytesToRead);
				if (array.Length == 1)
				{
					MySerialPortProcess.AddProductToList(array, MySerialPortProcess.SerialPortList[serialPort.PortName]);
				}
			}
			catch (System.Exception e2)
			{
				ErrorXMLProcess.ExceptionProcess(e2);
			}
		}

		private static void DetectPortForTimes(string portStr, int baudRate, SerialPort TheSerialPort)
		{
			try
			{
				byte[] buffer = new byte[]
				{
					192
				};
				TheSerialPort.BaudRate = baudRate;
				TheSerialPort.DiscardInBuffer();
				TheSerialPort.DiscardOutBuffer();
				TheSerialPort.Write(buffer, 0, 1);
			}
			catch (System.Exception e)
			{
				ErrorXMLProcess.ExceptionProcess(e);
			}
		}

		public static void DetectAllPorts(int baudRate)
		{
			try
			{
				if (!MySerialPortProcess.IfUpdatingFirmware)
				{
					lock (MySerialPortProcess._lock)
					{
						foreach (System.Collections.Generic.KeyValuePair<string, SerialPort> current in MySerialPortProcess.SerialPortList)
						{
							bool flag2 = false;
							foreach (DevicePort current2 in MySerialPortProcess.DevicePortList)
							{
								if (current.Key.Contains(current2.PortName))
								{
									flag2 = true;
									break;
								}
							}
							if (!flag2)
							{
								MySerialPortProcess.DetectPortForTimes(current.Key, baudRate, current.Value);
							}
						}
					}
				}
			}
			catch (System.Exception e)
			{
				ErrorXMLProcess.ExceptionProcess(e);
			}
		}

		private static bool CheckSerialPortExist(DevicePort product)
		{
			bool result;
			try
			{
				foreach (string current in MySerialPortProcess.SerialPortList.Keys)
				{
					if (current == product.PortName)
					{
						result = true;
						return result;
					}
				}
				result = false;
			}
			catch (System.Exception e)
			{
				ErrorXMLProcess.ExceptionProcess(e);
				result = false;
			}
			return result;
		}

		public static void ReadWriteCommand(byte[] commandBytes, DevicePort product, byte[] replyBytes)
		{
			try
			{
				if (!MySerialPortProcess.IfUpdatingFirmware)
				{
					lock (MySerialPortProcess._lock)
					{
						if (product.PortName != null && MySerialPortProcess.CheckSerialPortExist(product))
						{
							if (!MySerialPortProcess.SerialPortList[product.PortName].IsOpen)
							{
								MySerialPortProcess.SerialPortList[product.PortName].Open();
							}
							MySerialPortProcess.SerialPortList[product.PortName].Write(commandBytes, 0, commandBytes.Length);
							int num = 0;
							while (true)
							{
								num++;
								System.Threading.Thread.Sleep(10);
								if (MySerialPortProcess.SerialPortList[product.PortName].BytesToRead > 0)
								{
									break;
								}
								if (num > 20)
								{
									goto Block_9;
								}
							}
							System.Threading.Thread.Sleep(50);
							Block_9:
							int bytesToRead = MySerialPortProcess.SerialPortList[product.PortName].BytesToRead;
							byte[] array = new byte[bytesToRead];
							MySerialPortProcess.SerialPortList[product.PortName].Read(array, 0, bytesToRead);
							MySerialPortProcess.CheckReplyValue(array, replyBytes);
						}
					}
				}
			}
			catch (System.IO.IOException)
			{
			}
			catch (System.Exception e)
			{
				ErrorXMLProcess.ExceptionProcess(e);
			}
		}

		public static void CloseSerialPort()
		{
			try
			{
				foreach (System.Collections.Generic.KeyValuePair<string, SerialPort> current in MySerialPortProcess.SerialPortList)
				{
					current.Value.Close();
				}
			}
			catch (System.Exception e)
			{
				ErrorXMLProcess.ExceptionProcess(e);
			}
		}

		public static void OpenSerialPort()
		{
			try
			{
				foreach (System.Collections.Generic.KeyValuePair<string, SerialPort> current in MySerialPortProcess.SerialPortList)
				{
					current.Value.Open();
				}
			}
			catch (System.Exception e)
			{
				ErrorXMLProcess.ExceptionProcess(e);
			}
		}

		public static void ReadWriteCommandForFirmware1(byte[] commandBytes, DevicePort product, byte[] replyBytes)
		{
			try
			{
				lock (MySerialPortProcess._lock)
				{
					if (product.PortName != null && MySerialPortProcess.CheckSerialPortExist(product))
					{
						MySerialPortProcess.IfUpdatingFirmware = true;
						MySerialPortProcess.SerialPortList[product.PortName].Write(commandBytes, 0, commandBytes.Length);
						int num = 0;
						while (true)
						{
							num++;
							System.Threading.Thread.Sleep(10);
							if (MySerialPortProcess.SerialPortList[product.PortName].BytesToRead > 0)
							{
								break;
							}
							if (num > 60000)
							{
								goto Block_7;
							}
						}
						System.Threading.Thread.Sleep(50);
						Block_7:
						int bytesToRead = MySerialPortProcess.SerialPortList[product.PortName].BytesToRead;
						byte[] array = new byte[bytesToRead];
						MySerialPortProcess.SerialPortList[product.PortName].Read(array, 0, bytesToRead);
						MySerialPortProcess.CheckReplyValue(array, replyBytes);
					}
				}
			}
			catch (System.IO.IOException)
			{
			}
			catch (System.Exception e)
			{
				ErrorXMLProcess.ExceptionProcess(e);
			}
		}

		public static void ReadWriteCommandForFirmwareStop(byte[] commandBytes, DevicePort product, byte[] replyBytes)
		{
			try
			{
				lock (MySerialPortProcess._lock)
				{
					if (product.PortName != null && MySerialPortProcess.CheckSerialPortExist(product))
					{
						MySerialPortProcess.SerialPortList[product.PortName].Write(commandBytes, 0, commandBytes.Length);
						int num = 0;
						while (true)
						{
							num++;
							System.Threading.Thread.Sleep(10);
							if (MySerialPortProcess.SerialPortList[product.PortName].BytesToRead > 0)
							{
								break;
							}
							if (num > 60000)
							{
								goto Block_7;
							}
						}
						System.Threading.Thread.Sleep(50);
						Block_7:
						int bytesToRead = MySerialPortProcess.SerialPortList[product.PortName].BytesToRead;
						byte[] array = new byte[bytesToRead];
						MySerialPortProcess.SerialPortList[product.PortName].Read(array, 0, bytesToRead);
						MySerialPortProcess.CheckReplyValue(array, replyBytes);
					}
					MySerialPortProcess.IfUpdatingFirmware = false;
				}
			}
			catch (System.IO.IOException)
			{
			}
			catch (System.Exception e)
			{
				ErrorXMLProcess.ExceptionProcess(e);
			}
		}
	}
}
