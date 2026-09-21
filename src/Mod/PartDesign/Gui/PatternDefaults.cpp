// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PatternDefaults.h"

#include <algorithm>
#include <cmath>
#include <limits>

#include <BRepBndLib.hxx>
#include <Bnd_Box.hxx>
#include <Standard_Failure.hxx>
#include <TopoDS_Shape.hxx>
#include <gp_Dir.hxx>

#include <Base/Exception.h>
#include <Base/Precision.h>
#include <Mod/PartDesign/App/FeatureAddSub.h>
#include <Mod/PartDesign/App/FeatureLinearPattern.h>

namespace PartDesignGui
{

namespace
{
constexpr double clearFactor = 1.5;
constexpr double fallbackSpacing = 10.0;
// Tight boxes still carry a little floating-point noise; without this an exact 15 mm
// would round up to 16.
constexpr double roundingSlack = 1e-6;
}  // namespace

double roundUpSpacing(double value)
{
    const double step = value < 10.0 ? 0.1 : 1.0;
    return std::ceil(value / step - roundingSlack) * step;
}

namespace
{
/// Widens [lowest, highest] with shape's extent along dir (already normalized). Leaves
/// both untouched for a null or void shape.
void extendRangeAlongDirection(
    const TopoDS_Shape& shape,
    const Base::Vector3d& dir,
    double& lowest,
    double& highest
)
{
    if (shape.IsNull()) {
        return;
    }
    Bnd_Box box;
    // Tight and without the shape's tolerance, so a 10 mm pad measures 10 mm
    BRepBndLib::AddOptimal(shape, box, Standard_False, Standard_False);
    if (box.IsVoid()) {
        return;
    }
    double xmin, ymin, zmin, xmax, ymax, zmax;
    box.Get(xmin, ymin, zmin, xmax, ymax, zmax);
    for (double x : {xmin, xmax}) {
        for (double y : {ymin, ymax}) {
            for (double z : {zmin, zmax}) {
                const double along = Base::Vector3d(x, y, z) * dir;
                lowest = std::min(lowest, along);
                highest = std::max(highest, along);
            }
        }
    }
}

/// The spacing for a measured [lowest, highest] range along direction, or the fallback
/// when it comes out empty (nothing measured, or no extent along direction).
double spacingFromRange(double lowest, double highest, bool allowGaps)
{
    const double size = highest - lowest;
    if (!(size > Base::Precision::Confusion())) {
        return fallbackSpacing;
    }
    return roundUpSpacing(size * (allowGaps ? clearFactor : 1.0));
}

/// direction, normalized, or nullopt when it is too short to give a direction at all.
std::optional<Base::Vector3d> normalizedOrNullopt(const Base::Vector3d& direction)
{
    if (direction.Length() < Base::Precision::Confusion()) {
        return std::nullopt;
    }
    return Base::Vector3d(direction).Normalize();
}
}  // namespace

double suggestPatternSpacing(
    const std::vector<App::DocumentObject*>& originals,
    const Base::Vector3d& direction,
    bool allowGaps
)
{
    const auto dir = normalizedOrNullopt(direction);
    if (!dir) {
        return fallbackSpacing;
    }

    double lowest = std::numeric_limits<double>::max();
    double highest = std::numeric_limits<double>::lowest();
    for (App::DocumentObject* obj : originals) {
        auto* feature = freecad_cast<PartDesign::FeatureAddSub*>(obj);
        if (!feature) {
            continue;
        }
        TopoDS_Shape shape = feature->AddSubShape.getShape().getShape();
        if (shape.IsNull()) {
            continue;
        }
        shape.Move(feature->getLocation());
        extendRangeAlongDirection(shape, *dir, lowest, highest);
    }

    return spacingFromRange(lowest, highest, allowGaps);
}

double suggestPatternSpacing(
    const TopoDS_Shape& shape,
    const Base::Vector3d& direction,
    bool allowGaps
)
{
    const auto dir = normalizedOrNullopt(direction);
    if (!dir) {
        return fallbackSpacing;
    }

    double lowest = std::numeric_limits<double>::max();
    double highest = std::numeric_limits<double>::lowest();
    extendRangeAlongDirection(shape, *dir, lowest, highest);

    return spacingFromRange(lowest, highest, allowGaps);
}

std::optional<Base::Vector3d> patternDirection(
    const PartDesign::LinearPattern& pattern,
    const App::PropertyLinkSub& link
)
{
    if (!link.getValue()) {
        return std::nullopt;
    }
    try {
        gp_Dir dir = pattern.getDirectionFromProperty(link);
        // The feature works in its own frame; the panel and gizmos work in the body's
        dir.Transform(pattern.getLocation().Transformation());
        return Base::Vector3d(dir.X(), dir.Y(), dir.Z());
    }
    catch (const Base::Exception&) {
        return std::nullopt;
    }
    catch (const Standard_Failure&) {
        return std::nullopt;
    }
}

}  // namespace PartDesignGui
