using CAMV2.Core.XMLRecord;
using System;

namespace MyProtocol
{
	public class MyProtocolBytesTransfer
	{
		public static void SetFirmwareUpdateWrite(byte[] bytes, byte startOrStop)
		{
			bytes[0] = startOrStop;
		}

		public static void SetPowerOnOffBytes(byte[] bytes, byte commandType, byte power1, byte power2)
		{
			bytes[0] = commandType;
			bytes[1] = 0;
			bytes[2] = 192;
			bytes[3] = 0;
			bytes[4] = 0;
			bytes[5] = power1;
			bytes[6] = power2;
		}

		public static void SetDisplayModeCustomBytes(byte[] bytes, byte commandType, byte componentNum, byte modeType, byte eachLEDMode, byte colorTh, byte speed, byte[] g, byte[] r, byte[] b)
		{
			bytes[0] = commandType;
			bytes[1] = componentNum;
			bytes[2] = modeType;
			bytes[3] = eachLEDMode;
			bytes[4] = colorTh * 8 + speed;
			int num = 0;
			for (int i = 5; i < r.Length * 3 + 5; i++)
			{
				if ((i - 5) % 3 == 0)
				{
					bytes[i] = g[num];
				}
				else if ((i - 5) % 3 == 1)
				{
					bytes[i] = r[num];
				}
				else if ((i - 5) % 3 == 2)
				{
					bytes[i] = b[num];
					num++;
				}
			}
		}

		public static void SetNewHueBytes(byte[] bytes, byte commandType, byte componentNum, byte modeType, byte dir, byte sw, byte group, byte colorTh, byte ledea, byte speed, byte[] g, byte[] r, byte[] b)
		{
			bytes[0] = commandType;
			bytes[1] = componentNum;
			bytes[2] = modeType;
			bytes[3] = dir * 16 + sw * 8 + group;
			bytes[4] = colorTh * 32 + ledea * 8 + speed;
			int num = 0;
			for (int i = 5; i < r.Length * 3 + 5; i++)
			{
				if ((i - 5) % 3 == 0)
				{
					bytes[i] = g[num];
				}
				else if ((i - 5) % 3 == 1)
				{
					bytes[i] = r[num];
				}
				else if ((i - 5) % 3 == 2)
				{
					bytes[i] = b[num];
					num++;
				}
			}
		}

		public static void SetAudioNewHueBytes(byte[] bytes, byte commandType, byte componentNum, byte modeType, byte dir, byte sw, byte group, byte colorTh, byte ledea, byte speed, byte[] g, byte[] r, byte[] b)
		{
			try
			{
				bytes[0] = commandType;
				bytes[1] = componentNum;
				bytes[2] = modeType;
				bytes[3] = dir * 16 + sw * 8 + group;
				bytes[4] = colorTh * 32 + ledea * 8 + speed;
				int num = 0;
				int[] array = new int[120];
				for (int i = 0; i < 40; i++)
				{
					array[3 * i] = (int)g[num];
					array[3 * i + 1] = (int)r[num];
					array[3 * i + 2] = (int)b[num];
					num++;
				}
				num = 0;
				for (int i = 0; i < 60; i++)
				{
					string text = System.Convert.ToString(array[2 * num], 2).PadLeft(8, '0');
					string text2 = System.Convert.ToString(array[2 * num + 1], 2).PadLeft(8, '0');
					num++;
					text = text.Remove(4, 4);
					text2 = text2.Remove(4, 4);
					string value = text + text2;
					int num2 = System.Convert.ToInt32(value, 2);
					bytes[i + 5] = (byte)num2;
				}
			}
			catch (System.Exception e)
			{
				ErrorXMLProcess.ExceptionProcess(e);
			}
		}

		public static void SetDisplayModeBytes(byte[] bytes, byte commandType, byte componentNum, byte modeType, byte r, byte g, byte b, byte colorTh, byte ledEa, byte speed, byte optionByte)
		{
			bytes[0] = commandType;
			bytes[1] = componentNum;
			bytes[2] = modeType;
			bytes[3] = r;
			bytes[4] = g;
			bytes[5] = b;
			bytes[6] = (colorTh * 32 + ledEa * 8 + speed | optionByte);
		}

		public static void SetWriteVoltageCurrentBytes(byte[] bytes, byte commandType, byte componentNum, double setVoltage)
		{
			bytes[0] = commandType;
			bytes[1] = componentNum;
			bytes[2] = 192;
			bytes[3] = (bytes[4] = 0);
			bytes[5] = (byte)setVoltage;
			bytes[6] = (byte)((int)(setVoltage * 10.0) % 10 * 16 + (int)(setVoltage * 100.0) % 10);
		}

		public static void SetWriteDeviceIdBytes(byte[] bytes, byte commandType, byte idPart1, byte idPart2)
		{
			bytes[0] = commandType;
			bytes[1] = 0;
			bytes[2] = 192;
			bytes[3] = idPart1;
			bytes[4] = idPart2;
			bytes[5] = 0;
			bytes[6] = 0;
		}

		public static void SetReadBytes(byte[] bytes, byte readCommand, byte componentNum)
		{
			bytes[0] = readCommand;
			bytes[1] = componentNum;
		}

		public static double SetReplyVoltageCurrentBytes(byte[] bytes)
		{
			return System.Math.Round((double)bytes[3] + (double)(bytes[4] / 16) / 10.0 + (double)(bytes[4] % 16) / 100.0, 2);
		}

		public static int SetReplyRpmBytes(byte[] bytes)
		{
			return (int)bytes[3] * 256 + (int)bytes[4];
		}
	}
}
