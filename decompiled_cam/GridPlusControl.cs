using CAMV2.Core.XMLRecord;
using CAMV2.Data;
using DataXMLRecord;
using MyProtocol;
using System;
using System.Collections.Generic;

namespace CAMV2.Hardware.Detect
{
	public class GridPlusControl
	{
		private HardwareDetector.Computer _detector = null;

		private NotificationXMLRecord _notification = new NotificationXMLRecord();

		private byte[] _setWriteBytes = new byte[7];

		private byte[] _setReadBytes = new byte[2];

		private byte[] _readReply = new byte[5];

		private byte[] _writeReply = new byte[1];

		private static int FanCheckCounter = 0;

		private static int DCVoltageCheckCounter = 0;

		public GridPlusControl(HardwareDetector.Computer hd)
		{
			this._detector = hd;
		}

		public double RpmPercentToVoltage(int rpmPercent)
		{
			double result;
			if (rpmPercent == 0)
			{
				result = 0.0;
			}
			else
			{
				double num = 4.4 + ((double)rpmPercent - 20.0) * 0.1;
				if (num > 12.4)
				{
					num = 12.4;
				}
				result = num;
			}
			return result;
		}

		public void SetGridPlusVoltage(DevicePort product, double voltage)
		{
			MyProtocolBytesTransfer.SetWriteVoltageCurrentBytes(this._setWriteBytes, 68, 0, voltage);
			MySerialPortProcess.ReadWriteCommand(this._setWriteBytes, product, this._writeReply);
		}

		public void SetGridPlusVoltageByChannel(DevicePort product, double voltage, int channel)
		{
			MyProtocolBytesTransfer.SetWriteVoltageCurrentBytes(this._setWriteBytes, 68, (byte)channel, voltage);
			MySerialPortProcess.ReadWriteCommand(this._setWriteBytes, product, this._writeReply);
		}

		public void GetNamePort(DevicePort product, ref HardwareStructure.MyComputer _data, int which)
		{
			try
			{
				_data.get_GridFanHub()[which].set_Name(product.Device + "(" + product.PortName + ")");
				_data.get_GridFanHub()[which].set_PortName(product.PortName);
			}
			catch
			{
			}
		}

		public void GetAllCurrent(DevicePort product, ref HardwareStructure.MyComputer _data, int which)
		{
			try
			{
				_data.get_GridFanHub()[which].get_DCAmpere()[0] = 0.0;
				for (int i = 1; i < 7; i++)
				{
					MyProtocolBytesTransfer.SetReadBytes(this._setReadBytes, 133, (byte)i);
					MySerialPortProcess.ReadWriteCommand(this._setReadBytes, product, this._readReply);
					_data.get_GridFanHub()[which].get_DCAmpere()[i] = MyProtocolBytesTransfer.SetReplyVoltageCurrentBytes(this._readReply);
					_data.get_GridFanHub()[which].get_DCAmpere()[0] += _data.get_GridFanHub()[which].get_DCAmpere()[i];
				}
			}
			catch
			{
			}
		}

		public void GetAllRPM(DevicePort product, ref HardwareStructure.MyComputer _data, int which)
		{
			try
			{
				for (int i = 1; i < 7; i++)
				{
					MyProtocolBytesTransfer.SetReadBytes(this._setReadBytes, 138, (byte)i);
					MySerialPortProcess.ReadWriteCommand(this._setReadBytes, product, this._readReply);
					_data.get_GridFanHub()[which].get_RPM()[i] = MyProtocolBytesTransfer.SetReplyRpmBytes(this._readReply);
				}
			}
			catch
			{
			}
		}

		public void GetVoltage(DevicePort product, ref HardwareStructure.MyComputer _data, int which)
		{
			try
			{
				MyProtocolBytesTransfer.SetReadBytes(this._setReadBytes, 132, 0);
				MySerialPortProcess.ReadWriteCommand(this._setReadBytes, product, this._readReply);
				_data.get_GridFanHub()[which].set_DCVoltage(MyProtocolBytesTransfer.SetReplyVoltageCurrentBytes(this._readReply));
			}
			catch
			{
			}
		}

		public void GetRev2Voltage(DevicePort product, ref HardwareStructure.MyComputer _data, int which)
		{
			try
			{
				for (int i = 1; i < 7; i++)
				{
					MyProtocolBytesTransfer.SetReadBytes(this._setReadBytes, 132, (byte)i);
					MySerialPortProcess.ReadWriteCommand(this._setReadBytes, product, this._readReply);
					_data.get_GridFanHub()[which].get_ChannelDCVoltage()[i] = MyProtocolBytesTransfer.SetReplyVoltageCurrentBytes(this._readReply);
				}
			}
			catch
			{
			}
		}

		public void CalculateWatts(ref HardwareStructure.MyComputer _data, int which)
		{
			try
			{
				_data.get_GridFanHub()[which].get_Watt()[0] = 0.0;
				for (int i = 1; i < 7; i++)
				{
					_data.get_GridFanHub()[which].get_Watt()[i] = ((_data.get_GridFanHub()[which].get_RPM()[i] > 10) ? (_data.get_GridFanHub()[which].get_DCVoltage() * _data.get_GridFanHub()[which].get_DCAmpere()[i]) : 0.0);
					_data.get_GridFanHub()[which].get_Watt()[0] += _data.get_GridFanHub()[which].get_Watt()[i];
				}
			}
			catch
			{
			}
		}

		public void CalculateRev2Watts(ref HardwareStructure.MyComputer _data, int which)
		{
			try
			{
				_data.get_GridFanHub()[which].get_Watt()[0] = 0.0;
				for (int i = 1; i < 7; i++)
				{
					_data.get_GridFanHub()[which].get_Watt()[i] = ((_data.get_GridFanHub()[which].get_RPM()[i] > 10) ? (_data.get_GridFanHub()[which].get_ChannelDCVoltage()[i] * _data.get_GridFanHub()[which].get_DCAmpere()[i]) : 0.0);
					_data.get_GridFanHub()[which].get_Watt()[0] += _data.get_GridFanHub()[which].get_Watt()[i];
				}
			}
			catch
			{
			}
		}

		public void GetChannelStatus(ref HardwareStructure.MyComputer _data, int which)
		{
			try
			{
				for (int i = 0; i < 7; i++)
				{
					if (_data.get_GridFanHub()[which].get_Watt()[i] > 0.0 && _data.get_GridFanHub()[which].get_RPM()[i] > 0)
					{
						_data.get_GridFanHub()[which].get_IsChannelConnected()[i] = true;
					}
					else
					{
						_data.get_GridFanHub()[which].get_IsChannelConnected()[i] = false;
					}
				}
			}
			catch
			{
			}
		}

		private void WattCheck(System.Collections.Generic.KeyValuePair<AlertType, AlertLimit> _storeItem)
		{
			try
			{
				if (_storeItem.Key == 25)
				{
					if (_storeItem.Value.IfPreviStatusInLimitArray == null)
					{
						_storeItem.Value.IfPreviStatusInLimitArray = new bool[this._detector._aComputer.get_GridFanHub().Length];
						this._notification.SetBoolArrayTrue(_storeItem.Value.IfPreviStatusInLimitArray);
					}
					int num = 0;
					GridPlus[] gridFanHub = this._detector._aComputer.get_GridFanHub();
					for (int i = 0; i < gridFanHub.Length; i++)
					{
						GridPlus gridPlus = gridFanHub[i];
						this._notification.UpdateAlertLimit(25, new AlertLimit
						{
							UpperAlertValue = (double)gridPlus.get_WattNotifyUpperLimit(),
							LowerAlertValue = 0.0,
							IfPreviStatusInLimit = true
						});
						string name = gridPlus.get_Name();
						if (gridPlus.get_WattNotification() && name != null)
						{
							this._notification.Notifications(this, new AlertChangeArgs
							{
								Type = 25,
								Name = name,
								Value = gridPlus.get_Watt()[0],
								Limit = new AlertLimit
								{
									UpperAlertValue = _storeItem.Value.UpperAlertValue,
									LowerAlertValue = 0.0,
									IfPreviStatusInLimit = _storeItem.Value.IfPreviStatusInLimitArray[num]
								}
							});
						}
						if (gridPlus.get_Watt()[0] < _storeItem.Value.UpperAlertValue)
						{
							_storeItem.Value.IfPreviStatusInLimitArray[num] = true;
						}
						else
						{
							_storeItem.Value.IfPreviStatusInLimitArray[num] = false;
						}
						num++;
					}
				}
			}
			catch
			{
			}
		}

		private void VoltageCheck(System.Collections.Generic.KeyValuePair<AlertType, AlertLimit> _storeItem)
		{
			try
			{
				if (GridPlusControl.DCVoltageCheckCounter < 7)
				{
					GridPlusControl.DCVoltageCheckCounter++;
				}
				if (GridPlusControl.DCVoltageCheckCounter > 4)
				{
					if (_storeItem.Key == 24)
					{
						if (_storeItem.Value.IfPreviStatusInLimitArray == null)
						{
							_storeItem.Value.IfPreviStatusInLimitArray = new bool[this._detector._aComputer.get_GridFanHub().Length];
							this._notification.SetBoolArrayTrue(_storeItem.Value.IfPreviStatusInLimitArray);
						}
						int num = 0;
						GridPlus[] gridFanHub = this._detector._aComputer.get_GridFanHub();
						for (int i = 0; i < gridFanHub.Length; i++)
						{
							GridPlus gridPlus = gridFanHub[i];
							this._notification.UpdateAlertLimit(24, new AlertLimit
							{
								UpperAlertValue = gridPlus.get_VoltageNotifyUpperLimit(),
								LowerAlertValue = gridPlus.get_VoltageNotifyLowerLimit(),
								IfPreviStatusInLimit = true
							});
							string name = gridPlus.get_Name();
							if (gridPlus.get_VoltageNotification() && name != null)
							{
								this._notification.Notifications(this, new AlertChangeArgs
								{
									Type = 24,
									Name = name,
									Value = gridPlus.get_DCVoltage(),
									Limit = new AlertLimit
									{
										UpperAlertValue = _storeItem.Value.UpperAlertValue,
										LowerAlertValue = _storeItem.Value.LowerAlertValue,
										IfPreviStatusInLimit = _storeItem.Value.IfPreviStatusInLimitArray[num]
									}
								});
							}
							if (gridPlus.get_DCVoltage() < _storeItem.Value.UpperAlertValue && gridPlus.get_DCVoltage() > _storeItem.Value.LowerAlertValue)
							{
								_storeItem.Value.IfPreviStatusInLimitArray[num] = true;
							}
							else
							{
								_storeItem.Value.IfPreviStatusInLimitArray[num] = false;
							}
							num++;
						}
					}
				}
			}
			catch
			{
			}
		}

		private void FanWorkCheck(System.Collections.Generic.KeyValuePair<AlertType, AlertLimit> _storeItem)
		{
			try
			{
				if (_storeItem.Key == 26)
				{
					if (GridPlusControl.FanCheckCounter < 7)
					{
						GridPlusControl.FanCheckCounter++;
					}
					if (GridPlusControl.FanCheckCounter > 4)
					{
						if (_storeItem.Value.IfPreviStatusInLimitArray == null)
						{
							_storeItem.Value.IfPreviStatusInLimitArray = new bool[this._detector._aComputer.get_GridFanHub().Length * 6];
							this._notification.SetBoolArrayTrue(_storeItem.Value.IfPreviStatusInLimitArray);
						}
						int num = 0;
						GridPlus[] gridFanHub = this._detector._aComputer.get_GridFanHub();
						for (int i = 0; i < gridFanHub.Length; i++)
						{
							GridPlus gridPlus = gridFanHub[i];
							string name = gridPlus.get_Name();
							int num2 = 0;
							int num3 = 0;
							int[] rPM = gridPlus.get_RPM();
							for (int j = 0; j < rPM.Length; j++)
							{
								int num4 = rPM[j];
								if (num2 == 0)
								{
									num2++;
								}
								else
								{
									if (gridPlus.get_IsChannelConnected()[num2] && gridPlus.get_ChannelFanNotification()[num2 - 1])
									{
										this._notification.UpdateAlertLimit(26, new AlertLimit
										{
											UpperAlertValue = 100000.0,
											LowerAlertValue = (double)gridPlus.get_RpmNotifyLowerLimit()[num3],
											IfPreviStatusInLimit = true
										});
										this._notification.Notifications(this, new AlertChangeArgs
										{
											Type = 26,
											Name = name + "-Fan" + num2,
											Value = (double)num4,
											Limit = new AlertLimit
											{
												UpperAlertValue = _storeItem.Value.UpperAlertValue,
												LowerAlertValue = _storeItem.Value.LowerAlertValue,
												IfPreviStatusInLimit = _storeItem.Value.IfPreviStatusInLimitArray[num2 + num * 6]
											}
										});
									}
									if ((double)num4 > _storeItem.Value.LowerAlertValue)
									{
										_storeItem.Value.IfPreviStatusInLimitArray[num2 + num * 6] = true;
									}
									else
									{
										_storeItem.Value.IfPreviStatusInLimitArray[num2 + num * 6] = false;
									}
									num2++;
									num3++;
								}
							}
							num++;
						}
					}
				}
			}
			catch
			{
			}
		}

		public void AddWattNotification(int wattUpperLimit)
		{
			this._notification.SetAlertLimit(25, new AlertLimit
			{
				UpperAlertValue = (double)wattUpperLimit,
				LowerAlertValue = 0.0,
				IfPreviStatusInLimit = false
			});
			System.Action<System.Collections.Generic.KeyValuePair<AlertType, AlertLimit>> action = new System.Action<System.Collections.Generic.KeyValuePair<AlertType, AlertLimit>>(this.WattCheck);
			this._notification.AddCofResposity(25, action);
		}

		public void AddVoltageNotification(double voltageLowerLimit, double voltageUpperLimit)
		{
			this._notification.SetAlertLimit(24, new AlertLimit
			{
				UpperAlertValue = voltageUpperLimit,
				LowerAlertValue = voltageLowerLimit,
				IfPreviStatusInLimit = false
			});
			System.Action<System.Collections.Generic.KeyValuePair<AlertType, AlertLimit>> action = new System.Action<System.Collections.Generic.KeyValuePair<AlertType, AlertLimit>>(this.VoltageCheck);
			this._notification.AddCofResposity(24, action);
		}

		public void AddFanWorkNotification(int rpmLowerLimit)
		{
			this._notification.SetAlertLimit(26, new AlertLimit
			{
				UpperAlertValue = 100000.0,
				LowerAlertValue = (double)rpmLowerLimit,
				IfPreviStatusInLimit = false
			});
			System.Action<System.Collections.Generic.KeyValuePair<AlertType, AlertLimit>> action = new System.Action<System.Collections.Generic.KeyValuePair<AlertType, AlertLimit>>(this.FanWorkCheck);
			this._notification.AddCofResposity(26, action);
		}

		public void AddGridNotifications()
		{
			this.AddWattNotification(30);
			this.AddVoltageNotification(5.5, 12.5);
			this.AddFanWorkNotification(50);
		}

		public void SetGridNotifySetting(GridNotifySettingXMLStructure gridSettings, int which)
		{
			try
			{
				this._detector._aComputer.get_GridFanHub()[which].set_WattNotifyUpperLimit(gridSettings.WattUpperLimit);
				this._detector._aComputer.get_GridFanHub()[which].get_RpmNotifyLowerLimit()[0] = gridSettings.RpmLowerLimit1;
				this._detector._aComputer.get_GridFanHub()[which].get_RpmNotifyLowerLimit()[1] = gridSettings.RpmLowerLimit2;
				this._detector._aComputer.get_GridFanHub()[which].get_RpmNotifyLowerLimit()[2] = gridSettings.RpmLowerLimit3;
				this._detector._aComputer.get_GridFanHub()[which].get_RpmNotifyLowerLimit()[3] = gridSettings.RpmLowerLimit4;
				this._detector._aComputer.get_GridFanHub()[which].get_RpmNotifyLowerLimit()[4] = gridSettings.RpmLowerLimit5;
				this._detector._aComputer.get_GridFanHub()[which].get_RpmNotifyLowerLimit()[5] = gridSettings.RpmLowerLimit6;
				this._detector._aComputer.get_GridFanHub()[which].set_VoltageNotifyLowerLimit(gridSettings.VoltageLowerLimit);
				this._detector._aComputer.get_GridFanHub()[which].set_VoltageNotifyUpperLimit(gridSettings.VoltageUpperLimit);
				this._detector._aComputer.get_GridFanHub()[which].set_WattNotification(gridSettings.WattNotify);
				this._detector._aComputer.get_GridFanHub()[which].set_VoltageNotification(gridSettings.VoltageNotify);
				this._detector._aComputer.get_GridFanHub()[which].get_ChannelFanNotification()[0] = gridSettings.Fan1Notify;
				this._detector._aComputer.get_GridFanHub()[which].get_ChannelFanNotification()[1] = gridSettings.Fan2Notify;
				this._detector._aComputer.get_GridFanHub()[which].get_ChannelFanNotification()[2] = gridSettings.Fan3Notify;
				this._detector._aComputer.get_GridFanHub()[which].get_ChannelFanNotification()[3] = gridSettings.Fan4Notify;
				this._detector._aComputer.get_GridFanHub()[which].get_ChannelFanNotification()[4] = gridSettings.Fan5Notify;
				this._detector._aComputer.get_GridFanHub()[which].get_ChannelFanNotification()[5] = gridSettings.Fan6Notify;
			}
			catch
			{
			}
		}

		public int SetGridVoltageInCondition(double cpuOrGpuTemp, int which, int levels, int stepExtent, int[] customMode)
		{
			int result;
			for (int i = 0; i < levels; i++)
			{
				int num = i * stepExtent;
				if (cpuOrGpuTemp >= (double)num && cpuOrGpuTemp < (double)(num + stepExtent))
				{
					result = customMode[i];
					return result;
				}
			}
			result = 100;
			return result;
		}

		public int SetGridVoltageInCondition(double cpuOrGpuTemp, int which, int levels, int stepExtent, byte[] customMode)
		{
			int result;
			for (int i = 0; i < levels; i++)
			{
				int num = i * stepExtent;
				if (cpuOrGpuTemp >= (double)num && cpuOrGpuTemp < (double)(num + stepExtent))
				{
					result = (int)customMode[i];
					return result;
				}
			}
			result = 100;
			return result;
		}

		public void SetAllGridRev2ChannelFanSpeedFromMode(ref HardwareStructure.MyComputer data, System.Collections.Generic.List<GridXMLOverview> GridSettingsList)
		{
			try
			{
				if (data != null && data.get_CPUs() != null && data.get_CPUs()[0].get_Temperature() != 0.0)
				{
					double num = 0.0;
					for (int i = 0; i < data.get_CPUs().Length; i++)
					{
						num += data.get_CPUs()[i].get_Temperature();
					}
					num /= (double)data.get_CPUs().Length;
					double num2 = 0.0;
					int num3 = 0;
					if (data.get_GPUs() != null && data.get_GPUs().Length > 0)
					{
						for (int i = 0; i < data.get_GPUs().Length; i++)
						{
							if (data.get_GPUs()[i].get_Temperature() != -1.0 || data.get_GPUs()[i].get_Temperature() != 0.0)
							{
								num2 += data.get_GPUs()[i].get_Temperature();
								num3++;
							}
						}
					}
					num2 /= (double)((num3 > 0) ? num3 : 1);
					for (int j = 0; j < data.get_GridFanHub().Length; j++)
					{
						if (data.get_GridFanHub()[j].get_Name().Contains("GridRev2"))
						{
							for (int i = 1; i < 7; i++)
							{
								double num4 = num;
								if (GridSettingsList[j].ChannelSpeedChangeWith[i - 1] == "GPU")
								{
									bool flag = true;
									if (data == null || data.get_GPUs() == null || data.get_GPUs().Length == 0 || num2 == 0.0)
									{
										flag = false;
									}
									if (flag)
									{
										num4 = num2;
									}
								}
								if (num4 >= 100.0)
								{
									data.get_GridFanHub()[j].get_SetFanSpeedPercentOfChannel()[i] = 100;
								}
								else if (GridSettingsList[j].ChannelModeIndex[i - 1] == 0)
								{
									if (GridSettingsList[j].NameAndPort.Contains("GridRev2"))
									{
										data.get_GridFanHub()[j].get_SetFanSpeedPercentOfChannel()[i] = GridSettingsList[j].V2ManualRPMValue[i - 1];
									}
									else
									{
										data.get_GridFanHub()[j].get_SetFanSpeedPercentOfChannel()[i] = GridSettingsList[j].ManualRPMValue;
									}
								}
								else if (GridSettingsList[j].ChannelModeIndex[i - 1] == 1)
								{
									data.get_GridFanHub()[j].get_SetFanSpeedPercentOfChannel()[i] = Common.CalculateSlopeValue(num4, ConstStrings.GridSilentSpeedLevels);
								}
								else if (GridSettingsList[j].ChannelModeIndex[i - 1] == 2)
								{
									data.get_GridFanHub()[j].get_SetFanSpeedPercentOfChannel()[i] = Common.CalculateSlopeValue(num4, ConstStrings.GridPerformanceSpeedLevels);
								}
								else if (GridSettingsList[j].ChannelModeIndex[i - 1] - 3 < GridSettingsList[j].V2CustomMode.Count)
								{
									data.get_GridFanHub()[j].get_SetFanSpeedPercentOfChannel()[i] = Common.CalculateSlopeValue(num4, GridSettingsList[j].V2CustomMode[GridSettingsList[j].ChannelModeIndex[i - 1] - 3].SpeedTempCurve);
								}
								else
								{
									data.get_GridFanHub()[j].get_SetFanSpeedPercentOfChannel()[i] = Common.CalculateSlopeValue(num4, ConstStrings.GridPerformanceSpeedLevels);
								}
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

		public int GetRev2IndexByOrder(HardwareStructure.MyComputer data, int orderTh)
		{
			int num = -1;
			int result;
			try
			{
				int num2 = 1;
				if (data.get_GridFanHub() != null)
				{
					for (int i = 0; i < data.get_GridFanHub().Length; i++)
					{
						if (data.get_GridFanHub()[i].get_Name().Contains("GridRev2"))
						{
							num = i;
							if (num2 == orderTh)
							{
								result = num;
								return result;
							}
							num2++;
						}
					}
				}
			}
			catch (System.Exception e)
			{
				ErrorXMLProcess.ExceptionProcess(e);
			}
			result = num;
			return result;
		}
	}
}
