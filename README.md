# Secret Santa Generator

This Python script generates and edits Secret Santa assignment CSV files.

## Usage

```
python santaAlgorithm.py [PARTICIPANT_CSV]
```

The Participant CSV file is expected to adhere to the following format:

| Field Name                           | Field Description                                                                                                                                                                                             |
|--------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Name                                 | Full name of participant.                                                                                                                                                                                     |
| Simple Name                          | Simple name used for indexing. Consists only of lowercase alphanumeric characters (the letters a through z and digits 0 through 9)                                                                            |
| Subkinks (Large, Blob, Male, etc.)   | Preference level for each particular sub-kink given in the SUBKINKS array of the script. Has three values: "Yes", "Yes, but prefer not to", and "No". These exact values can also be specified in the script. |
| Prev Santas (2022, 2023, 2024, etc.) | If this participant has participated in a previous event, show the _simple name_ of the person they gave a gift to. This value may refer to a participant who is not participating in this year's event.      |
| Prompt Subkinks (Prompt Large, etc.) | For each subkink defined in the SUBKINKS array, indicates whether or not that subkink is present in this participant's prompt.                                                                                |

It will output a CSV file where the "Sender" column indicates the simple name of the sender, and the "Recipient" column indicates the simple name of the recipient.
