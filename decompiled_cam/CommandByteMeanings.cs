using System;

namespace MyProtocol
{
	public class CommandByteMeanings
	{
		public const byte WriteACVoltage = 65;

		public const byte WriteACCurrent = 66;

		public const byte WriteFrequence = 67;

		public const byte WriteDCVoltage = 68;

		public const byte WriteDCCurrent = 69;

		public const byte WritePowerOnOff = 70;

		public const byte WriteLedOnOff = 71;

		public const byte WriteBeeperVolume = 72;

		public const byte WriteTemperature = 73;

		public const byte WriteRPM = 74;

		public const byte WriteDisplayMode = 75;

		public const byte WriteFirmwareUpdateStart = 76;

		public const byte WriteDeviceNumberConnectionStatus = 77;

		public const byte WriteKrakenDisplayMode = 78;

		public const byte WriteTempVSSpeed = 79;

		public const byte WriteFirmwareUpdateStop = 80;

		public const byte ReadACVoltage = 129;

		public const byte ReadACCurrent = 130;

		public const byte ReadFrequence = 131;

		public const byte ReadDCVoltage = 132;

		public const byte ReadDCCurrent = 133;

		public const byte ReadPowerOnOff = 134;

		public const byte ReadLedOnOff = 135;

		public const byte ReadBeeperVolume = 136;

		public const byte ReadTemperature = 137;

		public const byte ReadRPM = 138;

		public const byte ReadDisplayMode = 139;

		public const byte ReadFirmwareVersion = 140;

		public const byte ReadLedConnectionStatus = 141;
	}
}
