import logoPng from "../../assets/images/logo.png"

export function Logo(props) {
  const { alt = "Logo", ...imgProps } = props

  return <img src={logoPng} alt={alt} {...imgProps} />
}
