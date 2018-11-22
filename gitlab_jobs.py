#!/usr/bin/env python3
"""
Show GitLab pipeline job durations.
"""

import argparse
import csv
from collections import defaultdict
from statistics import mean, median, stdev

# pip install python-gitlab
import gitlab


__version__ = '0.5'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--version', action='version',
        # *sigh* argparse converts the \n to a space anyway
        version="%(prog)s version {version},\n"
                "python-gitlab version {python_gitlab_version}".format(
                    version=__version__,
                    python_gitlab_version=gitlab.__version__,
                ),
    )
    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help='print more information',
    )
    parser.add_argument(
        '-g', '--gitlab',
        help='select configuration section in ~/.python-gitlab.cfg',
    )
    parser.add_argument(
        '-p', '--project', metavar='ID', required=True,
        help='select GitLab project (you can discover project IDs by running'
             ' gitlab project list --all)',
    )
    parser.add_argument(
        '-b', '--branch', '--ref', metavar='REF', default='master',
        help='select git branch',
    )
    parser.add_argument(
        '-l', '--limit', metavar='N', default=20, type=int,
        help='limit analysis to last N pipelines (max 100)',
    )
    parser.add_argument(
        '--csv', metavar='FILENAME',
        help='export raw data to CSV file',
    )
    args = parser.parse_args()

    gl = gitlab.Gitlab.from_config(args.gitlab)
    project = gl.projects.get(args.project)

    pipeline_durations = []
    job_durations = defaultdict(list)

    print("Last {n} successful pipelines of {project} {ref}:".format(
        n=args.limit, ref=args.branch, project=project.name))
    pipelines = project.pipelines.list(
        scope='finished', status='success', ref=args.branch,
        per_page=args.limit)
    for pipeline in pipelines:
        if args.verbose:
            template = (
                "  {id} (commit {sha} by {user[name]},"
                " duration {duration_min:.1f}m)"
            )
        else:
            template = "  {id} (commit {sha}, duration {duration_min:.1f}m)"
        # pipeline data returned in the list contains only a small subset
        # of information, so we need an extra HTTP GET to fetch duration
        # and user
        pipeline = project.pipelines.get(pipeline.id)
        pipeline_durations.append(pipeline.duration)
        duration_min = pipeline.duration / 60.0
        print(template.format(
            duration_min=duration_min, **pipeline.attributes))
        for job in pipeline.jobs.list(scope='success', all=True):
            job_durations[job.name].append(job.duration)
            if args.verbose:
                print("    {name:30}  {duration_min:4.1f}m".format(
                    name=job.name,
                    duration_min=job.duration / 60.0))

    if not pipeline_durations:
        print("\nNo pipelines found.")
        return

    print("\nSummary:")
    maxlen = max(len(name) for name in job_durations)
    digits = 4.1
    unit = "m", 60.0
    for job_name, durations in (
            sorted(job_durations.items()) + [('overall', pipeline_durations)]):
        print(
            "  {name:{maxlen}} "
            " min {min:{digits}f}{unit},"
            " max {max:{digits}f}{unit},"
            " avg {avg:{digits}f}{unit},"
            " median {median:{digits}f}{unit},"
            " stdev {stdev:{digits}f}{unit}"
            .format(
                name=job_name,
                maxlen=maxlen,
                digits=digits,
                unit=unit[0],
                min=min(durations) / unit[1],
                max=max(durations) / unit[1],
                avg=mean(durations) / unit[1],
                median=median(durations) / unit[1],
                stdev=stdev(durations) / unit[1] if len(durations) > 1 else 0,
            )
        )

    if args.csv:
        print("\nWriting {filename}...".format(filename=args.csv))
        with open(args.csv, 'w') as f:
            writer = csv.writer(f)
            for job_name, durations in sorted(job_durations.items()):
                writer.writerow([job_name] + durations)
            writer.writerow(['overall'] + pipeline_durations)


if __name__ == '__main__':
    main()
