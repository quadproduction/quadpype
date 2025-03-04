## QuadPype Deadline repository overlay

 This directory is an overlay for Deadline repository.
 It means that you can copy the whole hierarchy to Deadline repository and it
 should work.

 Logic:
 -----
 GlobalJobPreLoad
 -----

The `GlobalJobPreLoad` will retrieve the QuadPype executable path from the
`QuadPype` Deadline Plug-in's settings. Then it will call the executable to
retrieve the environment variables needed for the Deadline Job.
These environment variables are injected into rendering process.

Deadline triggers the `GlobalJobPreLoad.py` for each Worker as it starts the
Job.

*Note*: It also contains backward compatible logic to preserve functionality
for old Pype2 and non-QuadPype triggered jobs.

 Plugin
 ------
 For each render and publishing job the `QuadPype` Deadline Plug-in is checked
 for the configured location of the QuadPype executable (needs to be configured
 in `Deadline's Configure Plugins > QuadPype`) through `GlobalJobPreLoad`.
